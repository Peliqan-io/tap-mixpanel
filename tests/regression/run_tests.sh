#!/usr/bin/env bash
# Run regression tests inside a Python 3.11 container.
# Usage: bash run_tests.sh
#
# Required env vars (set before running):
#   TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME
#   TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET
#   TAP_MIXPANEL_PROJECT_ID
#   TAP_MIXPANEL_START_DATE     (optional)
#   TAP_MIXPANEL_EU_RESIDENCY   (optional, default "true")

set -euo pipefail

TAP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Running regression tests in python:3.11-slim"
echo "    Tap dir: $TAP_DIR"

docker run --rm \
  -v "$TAP_DIR":/tap \
  -w /tap \
  -e TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME="${TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME:?}" \
  -e TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET="${TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET:?}" \
  -e TAP_MIXPANEL_PROJECT_ID="${TAP_MIXPANEL_PROJECT_ID:?}" \
  -e TAP_MIXPANEL_START_DATE="${TAP_MIXPANEL_START_DATE:-2024-01-01T00:00:00Z}" \
  -e TAP_MIXPANEL_EU_RESIDENCY="${TAP_MIXPANEL_EU_RESIDENCY:-true}" \
  -e TAP_MIXPANEL_INCLUDE_STREAMS="${TAP_MIXPANEL_INCLUDE_STREAMS:-}" \
  -e AES_SECRET_KEY="peliqan-test-key" \
  python:3.11-slim \
  bash -c "
    apt-get update -qq && apt-get install -y -qq git > /dev/null
    python -m venv /venv
    /venv/bin/pip install -e . pytest -q
    cd tests/regression && /venv/bin/python -m pytest test_regression.py -v
  "
