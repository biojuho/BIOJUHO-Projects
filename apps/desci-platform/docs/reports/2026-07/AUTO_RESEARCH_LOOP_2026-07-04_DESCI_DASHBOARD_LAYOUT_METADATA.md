# AutoResearch Loop: Dashboard Layout Metadata

Date: 2026-07-04

## Goal

Make the dashboard layout guard auditable after a pass. The prior guard failed on horizontal overflow or clipped launch panels, but a passing JSON artifact only showed no failures; it did not record the measured layout state.

## A/B Test

- Baseline: `dashboard-readiness-refresh` layout checks are implicit in the absence of failures.
- Variant: browser smoke carries optional per-check metadata and records dashboard layout metrics in both the check entry and `launch_control.dashboard_layout`.
- KPI: the browser-smoke JSON records viewport width, document scroll width, and empty missing, zero-sized, and horizontally clipped target lists for the real dashboard check.

## Result

Variant wins. The direct browser-smoke artifact records:

- `viewportWidth`: 1280
- `scrollWidth`: 1280
- `missingTargets`: []
- `zeroSizedTargets`: []
- `horizontallyClippedTargets`: []

The same metrics are also embedded under `launch_control.dashboard_layout` for the dashboard launch-control artifact.

## Evidence

- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q`
  - Result: `45 passed`
- Direct browser smoke:
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var\browser-smoke-dashboard-layout-metadata-2026-07-04-rerun --json-out var\browser-smoke-dashboard-layout-metadata-2026-07-04-rerun.json --trace-on-failure-dir var\browser-smoke-dashboard-layout-metadata-2026-07-04-rerun-traces`
  - Result: `dashboard-readiness-refresh OK`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-layout-metadata-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-layout-metadata-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-layout-metadata-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/browser-smoke-dashboard-layout-metadata-2026-07-04-rerun.json`
- `apps/desci-platform/var/desci-browser-smoke-release-gate.json`
- `apps/desci-platform/var/release-gate-dashboard-layout-metadata-2026-07-04.json`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-layout-metadata-2026-07-04.json`
