# AutoResearch Loop: Release Gate Layout Summary

Date: 2026-07-04

## Goal

Lift dashboard layout evidence from the browser-smoke child artifact into the release-gate parent report. Browser smoke already recorded layout metrics, but release gate did not validate or summarize them.

## A/B Test

- Baseline: release gate treats `launch_control.dashboard_layout` as opaque child JSON.
- Variant: release gate validates optional dashboard layout metrics and promotes them into `browser_launch_control_summary.dashboard_layout`.
- KPI: parent release-gate JSON shows no horizontal overflow, no missing targets, no zero-sized targets, and no clipped launch targets for the dashboard readiness check.

## Result

Variant wins. The parent release-gate report now records:

- `viewportWidth`: 1280
- `scrollWidth`: 1280
- `missingTargets`: []
- `zeroSizedTargets`: []
- `horizontallyClippedTargets`: []
- `hasHorizontalOverflow`: false
- `hasLayoutTargetFailures`: false

Release gate also fails JSON evidence validation when a browser child artifact reports dashboard horizontal overflow or non-empty missing, zero-sized, or clipped target lists.

## Evidence

- `python -m py_compile scripts\release_gate.py scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_release_gate.py backend\tests\test_browser_smoke.py -q`
  - Result: `153 passed`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-layout-parent-summary-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-layout-parent-summary-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-layout-parent-summary-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/release-gate-dashboard-layout-parent-summary-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-layout-parent-summary-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-layout-parent-summary-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
