"""
Per-stream live discover helper.

Calls tap_mixpanel.schema.get_schema directly for each stream listed in
TAP_MIXPANEL_INCLUDE_STREAMS. Used when full --discover fails because some
upstream endpoints are blocked by the Mixpanel plan (e.g. events/properties/top
returns 402).

Output: JSON catalog on stdout.

Required env:
    TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME
    TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET
    TAP_MIXPANEL_PROJECT_ID
    TAP_MIXPANEL_INCLUDE_STREAMS   (comma-separated)
    TAP_MIXPANEL_EU_RESIDENCY      (optional, default "true")
"""
import json
import os
import sys

from singer import metadata

from tap_mixpanel.client import MixpanelClient
from tap_mixpanel.schema import get_schema
from tap_mixpanel.streams import STREAMS


def main():
    include = os.environ.get("TAP_MIXPANEL_INCLUDE_STREAMS", "").split(",")
    include = [s.strip() for s in include if s.strip()]
    if not include:
        print("ERROR: TAP_MIXPANEL_INCLUDE_STREAMS must be set", file=sys.stderr)
        sys.exit(2)

    api_domain = (
        "eu.mixpanel.com"
        if os.environ.get("TAP_MIXPANEL_EU_RESIDENCY", "true").lower() == "true"
        else "mixpanel.com"
    )
    properties_flag = "true"

    with MixpanelClient(
        service_account_username=os.environ["TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME"],
        service_account_secret=os.environ["TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET"],
        project_id=os.environ["TAP_MIXPANEL_PROJECT_ID"],
        api_domain=api_domain,
        request_timeout=300,
        user_agent="peliqan-regression/1.0",
    ) as client:
        client.__api_domain = api_domain

        streams_out = []
        for stream_id in include:
            stream_meta = STREAMS[stream_id]
            schema = get_schema(client, properties_flag, stream_id)

            mdata = metadata.get_standard_metadata(
                schema=schema,
                key_properties=stream_meta.key_properties,
                valid_replication_keys=stream_meta.replication_keys,
                replication_method=stream_meta.replication_method,
            )
            mdata_map = metadata.to_map(mdata)
            if stream_meta.replication_keys:
                mdata_map = metadata.write(
                    mdata_map,
                    ("properties", stream_meta.replication_keys[0]),
                    "inclusion",
                    "automatic",
                )
            mdata_list = metadata.to_list(mdata_map)

            for entry in mdata_list:
                entry.setdefault("metadata", {})["selected"] = True

            streams_out.append({
                "tap_stream_id": stream_id,
                "stream": stream_id,
                "schema": schema,
                "key_properties": list(stream_meta.key_properties),
                "replication_method": stream_meta.replication_method,
                "replication_key": (list(stream_meta.replication_keys) or [None])[0],
                "metadata": mdata_list,
            })

        print(json.dumps({"streams": streams_out}))


if __name__ == "__main__":
    main()
