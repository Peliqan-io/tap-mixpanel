"""
Shared fixtures and utilities for tap-mixpanel regression tests.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REGRESSION_DIR = Path(__file__).parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
TAP_CMD = str(Path(sys.executable).parent / "tap-mixpanel")

REQUIRED_ENV = [
    "TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME",
    "TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET",
    "TAP_MIXPANEL_PROJECT_ID",
]


def build_config():
    missing = [v for v in REQUIRED_ENV if not os.getenv(v)]
    if missing:
        pytest.skip(f"Missing required env vars: {missing}")

    return {
        "service_account_username": os.environ["TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME"],
        "service_account_secret": os.environ["TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET"],
        "project_id": os.environ["TAP_MIXPANEL_PROJECT_ID"],
        "start_date": os.getenv("TAP_MIXPANEL_START_DATE", "2024-01-01T00:00:00Z"),
        "date_window_size": os.getenv("TAP_MIXPANEL_DATE_WINDOW_SIZE", "30"),
        "attribution_window": os.getenv("TAP_MIXPANEL_ATTRIBUTION_WINDOW", "5"),
        "project_timezone": os.getenv("TAP_MIXPANEL_PROJECT_TIMEZONE", "Europe/Brussels"),
        "select_properties_by_default": "true",
        "eu_residency": os.getenv("TAP_MIXPANEL_EU_RESIDENCY", "true"),
        "request_timeout": 300,
        "user_agent": "peliqan-regression/1.0",
    }


def _tap_env():
    env = os.environ.copy()
    env.setdefault("AES_SECRET_KEY", "peliqan-test-key")
    return env


def _per_stream_discover():
    """Run the helper script to do live per-stream discover.

    Bypasses full --discover when some upstream endpoints (e.g.
    events/properties/top) are blocked by the project's plan.
    """
    helper = Path(__file__).parent / "_discover_helper.py"
    result = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, env=_tap_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"per-stream discover failed: {result.stderr[-2000:]}")
    return json.loads(result.stdout)


def discover_catalog(config_path):
    """Build the catalog used for sync.

    - If TAP_MIXPANEL_INCLUDE_STREAMS is set, run a live per-stream discover
      via _discover_helper.py (calls tap_mixpanel.schema.get_schema directly).
    - Otherwise run the standard tap-mixpanel --discover.
    """
    if os.getenv("TAP_MIXPANEL_INCLUDE_STREAMS"):
        return _per_stream_discover()

    result = subprocess.run(
        [TAP_CMD, "--config", config_path, "--discover"],
        capture_output=True, text=True, env=_tap_env()
    )
    if result.returncode != 0:
        raise RuntimeError(f"discover failed: {result.stderr[-2000:]}")
    return json.loads(result.stdout)


def select_all_streams(catalog):
    """Mark every stream and every field as selected in the catalog metadata."""
    for stream in catalog.get("streams", []):
        for entry in stream.get("metadata", []):
            entry.setdefault("metadata", {})["selected"] = True
    return catalog


def write_catalog(catalog):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(catalog, tmp)
    tmp.close()
    return tmp.name


@pytest.fixture(scope="session")
def config_file():
    config = build_config()
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, tmp)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture(scope="session")
def catalog_file(config_file):
    catalog = discover_catalog(config_file)
    select_all_streams(catalog)
    path = write_catalog(catalog)
    yield path
    os.unlink(path)


def run_tap(config_path, catalog_path=None, extra_args=None):
    cmd = [TAP_CMD, "--config", config_path]
    if catalog_path:
        cmd += ["--catalog", catalog_path]
    cmd += (extra_args or [])
    result = subprocess.run(cmd, capture_output=True, text=True, env=_tap_env())
    return result.stdout, result.stderr, result.returncode


def parse_messages(stdout):
    schemas, records, states = {}, {}, []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = msg.get("type")
        if t == "SCHEMA":
            schemas[msg["stream"]] = msg["schema"]
            records.setdefault(msg["stream"], [])
        elif t == "RECORD":
            records.setdefault(msg["stream"], []).append(msg["record"])
        elif t == "STATE":
            states.append(msg["value"])
    return schemas, records, states
