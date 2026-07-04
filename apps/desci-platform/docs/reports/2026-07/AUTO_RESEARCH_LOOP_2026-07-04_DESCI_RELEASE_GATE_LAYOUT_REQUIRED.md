# AutoResearch Loop: Release Gate Layout Required

Date: 2026-07-04

## Goal

Make dashboard layout evidence mandatory for browser launch-control artifacts. The parent release gate could validate layout metrics when present, but an older or incomplete browser-smoke JSON could still omit them and pass.

## A/B Test

- Baseline: `launch_control.dashboard_layout` is optional.
- Variant: release gate requires `launch_control.dashboard_layout` for `dashboard-readiness-refresh` artifacts and fails JSON evidence validation when it is missing.
- KPI: current runtime browser release gate passes with layout metrics, while a missing-layout fixture fails closed.

## Result

Variant wins. Release gate now requires dashboard layout evidence for the dashboard readiness launch-control check. The required runtime path still passes and reports:

- `viewportWidth`: 1280
- `scrollWidth`: 1280
- `hasHorizontalOverflow`: false
- `hasLayoutTargetFailures`: false

## Evidence

- `python -m py_compile scripts\release_gate.py scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_release_gate.py backend\tests\test_browser_smoke.py -q`
  - Result: `154 passed`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-layout-required-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-layout-required-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-layout-required-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/release-gate-dashboard-layout-required-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-layout-required-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-layout-required-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
