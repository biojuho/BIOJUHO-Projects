# AutoResearch Loop: Release Gate Copy Coverage

Date: 2026-07-04

## Goal

Lift individual launch action copy coverage into release-gate validation and parent summaries. Browser smoke recorded six validated action copy paths, but release gate did not validate or expose that coverage.

## A/B Test

- Baseline: `launch_action_copy_coverage` is opaque child JSON.
- Variant: release gate requires the coverage object for dashboard launch-control evidence, validates counts and IDs, and promotes it into `browser_launch_control_summary`.
- KPI: parent release-gate JSON reports six expected action IDs, six validated IDs, zero failed IDs, and fails closed if the coverage object is missing.

## Result

Variant wins. The parent release-gate summary records:

- `expected_count`: 6
- `validated_count`: 6
- `failed_count`: 0
- `expected_action_ids`: `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, `grobid`
- `validated_action_ids`: `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, `grobid`
- `failed_action_ids`: []

## Evidence

- `python -m py_compile scripts\release_gate.py scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_release_gate.py backend\tests\test_browser_smoke.py -q`
  - Result: `156 passed`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-copy-coverage-parent-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-copy-coverage-parent-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-copy-coverage-parent-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/release-gate-dashboard-copy-coverage-parent-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-copy-coverage-parent-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-copy-coverage-parent-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
