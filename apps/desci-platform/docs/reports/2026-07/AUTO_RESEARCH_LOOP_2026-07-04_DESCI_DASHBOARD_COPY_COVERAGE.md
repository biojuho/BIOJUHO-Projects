# AutoResearch Loop: Dashboard Copy Coverage

Date: 2026-07-04

## Goal

Make individual launch action copy coverage durable in browser-smoke JSON. The browser test clicked every individual launch action copy button, but the artifact did not record which action IDs were validated.

## A/B Test

- Baseline: all copy clicks are implicit in a passing `dashboard-readiness-refresh` check.
- Variant: the browser check records `launch_action_copy_coverage` under `launch_control` with expected, validated, and failed action IDs.
- KPI: browser-smoke JSON reports six expected actions, six validated actions, and zero failed action copies.

## Result

Variant wins. The browser-smoke artifact now records:

- `expected_action_ids`: `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, `grobid`
- `validated_action_ids`: `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, `grobid`
- `failed_action_ids`: []
- `expected_count`: 6
- `validated_count`: 6
- `failed_count`: 0

## Evidence

- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q`
  - Result: `46 passed`
- Direct browser smoke:
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var\browser-smoke-dashboard-copy-coverage-2026-07-04 --json-out var\browser-smoke-dashboard-copy-coverage-2026-07-04.json --trace-on-failure-dir var\browser-smoke-dashboard-copy-coverage-2026-07-04-traces`
  - Result: `dashboard-readiness-refresh OK`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-copy-coverage-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-copy-coverage-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-copy-coverage-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/browser-smoke-dashboard-copy-coverage-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-copy-coverage-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-copy-coverage-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-copy-coverage-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
