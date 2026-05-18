# tap-mixpanel — Python 3.11 Regression Tests

Before/after parity test for the Python 3.9 → 3.11 migration.

## Strategy

1. **Capture** baseline on pre-migration `master` + Python 3.9 (records full schemas, state-key names, and union of record field names per stream).
2. **Compare** on migration branch + Python 3.11 — assert schemas unchanged, no streams dropped, all baseline fields still present.

## Files

| File | Purpose |
| --- | --- |
| `conftest.py` | Shared fixtures: config builder, per-stream discover, sync runner, message parser |
| `_discover_helper.py` | Calls `tap_mixpanel.schema.get_schema` directly so we can discover individual streams without tripping endpoints blocked by the project's plan |
| `capture.py` | Standalone script — run once on Python 3.9 to write `baseline/` |
| `test_regression.py` | pytest suite — run on Python 3.11 to verify parity |
| `run_capture.sh` | Wrapper that runs `capture.py` in `python:3.9-slim` Docker |
| `run_tests.sh` | Wrapper that runs pytest in `python:3.11-slim` Docker |
| `baseline/` | Committed reference output: schemas, state keys, record fields, catalog, meta |

## Usage

Required env vars:

```bash
export TAP_MIXPANEL_SERVICE_ACCOUNT_USERNAME=...
export TAP_MIXPANEL_SERVICE_ACCOUNT_SECRET=...
export TAP_MIXPANEL_PROJECT_ID=...
export TAP_MIXPANEL_EU_RESIDENCY=true          # optional, default true
export TAP_MIXPANEL_INCLUDE_STREAMS=engage     # comma-separated; if unset, full --discover
export TAP_MIXPANEL_START_DATE=2024-01-01T00:00:00Z  # optional
```

### Capture baseline (pre-migration code on Python 3.9)

Run inside a worktree checked out at `master` (or whatever the pre-migration ref is):

```bash
git worktree add /tmp/tap-mixpanel-master master
cp -r tests/regression /tmp/tap-mixpanel-master/tests/regression
cd /tmp/tap-mixpanel-master
bash tests/regression/run_capture.sh
cp -r tests/regression/baseline /Users/.../tap-mixpanel/tests/regression/
git worktree remove /tmp/tap-mixpanel-master
```

### Run tests (migration branch on Python 3.11)

```bash
bash tests/regression/run_tests.sh
```

## Caveats

- The Mixpanel project this was validated against (`2891144`) is on a plan that returns 402 on `events/properties/top`, `cohorts/list`, `funnels/list`, and `annotations`. Only the `engage` stream's API is accessible.
- `TAP_MIXPANEL_INCLUDE_STREAMS` lets you scope discover to just the streams the account can reach. Once a project with full API access is available, drop the env var to test the full stream set.
- `_discover_helper.py` uses `tap_mixpanel.schema.get_schema` directly, so it captures the **enriched** engage schema (8 properties) — not the bare bundled schema (1 property).
