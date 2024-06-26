import datetime
import pytz
import singer
from singer.utils import strftime
from singer import Transformer

LOGGER = singer.get_logger()

# De-nest properties for engage and export endpoints
def denest_properties(record, properties_node):
    new_record = record
    properties = record.get(properties_node)
    if properties:
        for key, val in record[properties_node].items():
            if key[0:1] == '$':
                new_key = 'mp_reserved_{}'.format(key[1:])
                # change this to regex
            else:
                new_key = key
            new_record[new_key] = val
        new_record.pop(properties_node, None)
    return new_record


# Time conversion from $time integer using project_timezone
# Reference: https://help.mixpanel.com/hc/en-us/articles/115004547203-Manage-Timezones-for-Projects-in-Mixpanel#exporting-data-from-mixpanel
def transform_event_times(record, project_timezone):
    new_record = record
    timezone = pytz.timezone(project_timezone)

    # Create beginning_datetime: beginning of epoch time in project timezone
    naive_time = datetime.time(0, 0)
    date = datetime.date(1970, 1, 1)
    naive_datetime = datetime.datetime.combine(date, naive_time)
    # Move 1970-01-01T00:00:00Z to Mixpanel project timezone.
    # For example, if Mixpanel timezone is in Eastern Time (UTC-5:00) then it calculates 1969-12-31T19:00:00-5:00.
    beginning_datetime = pytz.utc.localize(naive_datetime).astimezone(timezone)

    # Get integer time
    time_int = int(record.get('time'))

    # Create new_time_utc by adding seconds to beginning_datetime, normalizing,
    #   and converting to string
    add_seconds = datetime.timedelta(seconds=time_int)
    new_time = beginning_datetime + add_seconds

    # 'normalize' accounts for daylight savings time
    new_time_utc_str = strftime(timezone.normalize(new_time).astimezone(pytz.utc))
    new_record['time'] = new_time_utc_str

    return new_record

def transform_datetime(this_dttm):
        with Transformer() as transformer:
            new_dttm = transformer._transform_datetime(this_dttm)
        return new_dttm


# Remove leading $ from engage $distinct_id
def transform_engage(record):
    new_record = record
    distinct_id = record.get('$distinct_id')
    new_record['distinct_id'] = distinct_id
    new_record.pop('$distinct_id', None)
    return new_record


# Funnels: combine parent record with each date record
def transform_funnels(record, parent_record):
    record.update(parent_record)
    return record


# Cohort Members: provide all distinct_id's for each cohort_id
def transform_cohort_members(record, parent_record):
    cohort_id = parent_record.get('id')
    distinct_id = record.get('$distinct_id')
    new_record = {}
    new_record['distinct_id'] = distinct_id
    new_record['cohort_id'] = cohort_id
    return new_record


# Run other transforms, as needed: denest_list_nodes, transform_conversation_parts
def transform_record(record, stream_name, project_timezone, parent_record=None):
    if stream_name == 'engage':
        trans_json = transform_engage(record)
        new_record = denest_properties(trans_json, '$properties')
    elif stream_name == 'export':
        denested_json = denest_properties(record, 'properties')
        new_record = transform_event_times(denested_json, project_timezone)
    elif stream_name == 'funnels':
        new_record = transform_funnels(record, parent_record)
    elif stream_name == 'cohort_members':
        new_record = transform_cohort_members(record, parent_record)
    else:
        new_record = record

    return new_record
