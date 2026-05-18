"""
Regression tests — run on Python 3.11 after migration.
Compares live output against baseline/ files captured on Python 3.9.
"""
import json
import sys

import pytest

from conftest import BASELINE_DIR, parse_messages, run_tap


def load_baseline(filename):
    path = BASELINE_DIR / filename
    if not path.exists():
        pytest.skip(f"Baseline file not found: {path}. Run capture.py on Python 3.9 first.")
    return json.loads(path.read_text())


def extract_state_keys(states):
    keys = {}
    for state in states:
        for stream, bookmark in state.get("bookmarks", {}).items():
            keys[stream] = sorted(bookmark.keys()) if isinstance(bookmark, dict) else []
    return keys


def extract_record_fields(records):
    fields = {}
    for stream, stream_records in records.items():
        all_fields = set()
        for record in stream_records:
            all_fields.update(record.keys())
        fields[stream] = sorted(all_fields)
    return fields


@pytest.fixture(scope="session")
def live_output(config_file, catalog_file):
    stdout, stderr, returncode = run_tap(config_file, catalog_path=catalog_file)
    return stdout, stderr, returncode


@pytest.fixture(scope="session")
def parsed(live_output):
    stdout, _, _ = live_output
    return parse_messages(stdout)


def test_python_version():
    """Confirm we are actually running on Python 3.11."""
    major, minor = sys.version_info[:2]
    assert (major, minor) >= (3, 11), (
        f"Expected Python >=3.11, got {major}.{minor}. "
        "Run these tests inside the Python 3.11 container."
    )


def test_tap_exits_clean(live_output):
    _, stderr, returncode = live_output
    assert returncode == 0, f"tap exited {returncode}.\nstderr (last 2000 chars):\n{stderr[-2000:]}"


def test_schemas_unchanged(parsed):
    """SCHEMA messages must exactly match the Python 3.9 baseline."""
    baseline = load_baseline("schemas.json")
    schemas, _, _ = parsed

    missing = set(baseline.keys()) - set(schemas.keys())
    assert not missing, f"Streams dropped after migration: {missing}"

    for stream, expected_schema in baseline.items():
        actual_schema = schemas.get(stream)
        assert actual_schema == expected_schema, (
            f"Schema changed for stream '{stream}' after migration.\n"
            f"Run a JSON diff between baseline/schemas.json and the current output."
        )


def test_state_keys_unchanged(parsed):
    """Bookmark key names in STATE messages must match baseline."""
    baseline = load_baseline("state_keys.json")
    _, _, states = parsed

    if not states:
        pytest.skip("No STATE messages emitted — skipping state key comparison.")

    actual_keys = extract_state_keys(states)

    for stream, expected_keys in baseline.items():
        actual = actual_keys.get(stream, [])
        assert actual == expected_keys, (
            f"State keys changed for '{stream}'.\n"
            f"Expected: {expected_keys}\n"
            f"Got:      {actual}"
        )


def test_record_fields_unchanged(parsed):
    """Field names seen in RECORD messages must be a superset of baseline fields."""
    baseline = load_baseline("record_fields.json")
    _, records, _ = parsed

    actual_fields = extract_record_fields(records)

    for stream, expected_fields in baseline.items():
        if stream not in actual_fields:
            pytest.fail(f"Stream '{stream}' emitted records on 3.9 but none on 3.11.")

        actual = set(actual_fields[stream])
        expected = set(expected_fields)
        dropped = expected - actual
        assert not dropped, (
            f"Fields dropped from '{stream}' after migration: {dropped}"
        )


def test_no_new_unexpected_fields(parsed):
    """Warn if new fields appear in records after migration (not a hard failure)."""
    baseline = load_baseline("record_fields.json")
    _, records, _ = parsed
    actual_fields = extract_record_fields(records)

    for stream, actual in actual_fields.items():
        expected = set(baseline.get(stream, []))
        new_fields = set(actual) - expected
        if new_fields:
            print(f"\nINFO: New fields in '{stream}' on 3.11 (not in baseline): {new_fields}")
