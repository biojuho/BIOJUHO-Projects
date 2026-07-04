# AutoResearch Loop: Release Gate Valid PNG Screenshots

Date: 2026-07-04

## Goal

Strengthen screenshot evidence from path existence to image proof. The previous release gate validated that `screenshot_artifacts` paths existed, but an empty or bogus file at that path could still satisfy the parent report.

## A/B Test

- Baseline: release gate accepts any existing screenshot artifact path.
- Variant: release gate parses each browser screenshot as PNG structure, requiring the PNG signature, IHDR chunk, positive dimensions, and an IEND chunk.
- KPI: real browser-smoke dashboard screenshots pass with positive dimensions, while invalid placeholder files fail JSON evidence validation.

## Result

Variant wins. The parent release-gate JSON now exposes valid and invalid PNG counts:

- `valid_png_count`: 1
- `invalid_png_count`: 0
- `has_invalid_screenshot_artifacts`: false
- Dashboard screenshot dimensions: `1280x2646`

Invalid screenshot files are reported as validation failures and promoted into `browser_screenshot_artifact_summary.invalid_png_paths`.

## Evidence

- `python -m py_compile scripts\release_gate.py scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_release_gate.py backend\tests\test_browser_smoke.py -q`
  - Result: `151 passed`
- Targeted runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-browser-valid-png-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-browser-valid-png-summary-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-release-gate-valid-png-screenshots-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/release-gate-browser-valid-png-summary-2026-07-04.json`
- `apps/desci-platform/var/release-gate-browser-valid-png-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-release-gate-valid-png-screenshots-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
