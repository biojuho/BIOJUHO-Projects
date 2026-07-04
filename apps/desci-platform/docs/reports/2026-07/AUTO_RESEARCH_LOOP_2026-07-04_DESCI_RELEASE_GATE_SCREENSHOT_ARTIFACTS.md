# AutoResearch Loop: Release Gate Screenshot Artifacts

Date: 2026-07-04

## Goal

Close the evidence gap between browser-smoke success screenshots and release-gate parent reports. Browser smoke could capture a successful dashboard PNG, but release gate did not validate or summarize that artifact, so a parent release JSON could pass without proving the screenshot file still existed.

## A/B Test

- Baseline: `browser_smoke.py --screenshot-dir ...` writes `screenshot_artifacts` only in the child browser-smoke JSON.
- Variant: release gate passes `--runtime-browser-screenshot-dir`, validates `screenshot_artifacts`, fails closed on missing PNG paths, and promotes screenshot counts and paths into the parent JSON.
- KPI: parent release-gate JSON exposes one existing screenshot artifact for `dashboard-readiness-refresh` with zero missing screenshot artifacts.

## Result

Variant wins. The parent release-gate report now includes `browser_screenshot_artifact_summary` and `artifact_summary` fields for screenshot evidence:

- `screenshot_artifact_count`: 1
- `existing_count`: 1
- `missing_count`: 0
- `has_missing_screenshot_artifacts`: false
- `checks`: `dashboard-readiness-refresh`

The release gate also reports missing screenshot paths as JSON evidence validation failures.

## Evidence

- `python -m py_compile scripts\release_gate.py scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_release_gate.py backend\tests\test_browser_smoke.py -q`
  - Result: `150 passed`
- Targeted runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-browser-success-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-browser-success-screenshot-summary-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-release-gate-screenshot-artifacts-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/release-gate-browser-success-screenshot-summary-2026-07-04.json`
- `apps/desci-platform/var/release-gate-browser-success-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-release-gate-screenshot-artifacts-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
