# Auto Research Loop - AgriGuard Readiness Browser Smoke Evidence - 2026-07-06

## Objective

Surface safe browser-smoke evidence in the AgriGuard launch readiness summary. The guarded compose path already records `child_reports.browser_smoke`, but the readiness summary previously reduced the launch report without forwarding the browser-smoke status, counts, or artifact path.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READINESS_BROWSER_SMOKE_EVIDENCE_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/launch_compose.py`
  - Extends the browser-smoke child report summary with safe runtime fields, failed-name lists, and aggregate counts.
- `apps/AgriGuard/scripts/summarize_launch_readiness.py`
  - Adds a safe `reports.launch.browser_smoke` subset to readiness JSON.
  - Renders a `Browser Smoke Evidence` markdown table when browser-smoke child report data is present.
  - Skips incomplete count ratios when preflight blocks before browser smoke runs.
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
  - Verifies launch reports carry the enriched browser-smoke child report summary.
- `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Verifies readiness summaries expose pending browser-smoke paths for blocked preflight and pass counts for ready browser-smoke evidence.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Result: `25 passed in 0.85s`
- `python apps\AgriGuard\scripts\summarize_launch_readiness.py --app-root apps\AgriGuard --launch-report-json var\agriguard-guarded-launch-launch-report.json --env-validation-json var\agriguard-guarded-launch-env-validation.json --operator-packet-json var\agriguard-guarded-launch-operator-packet.json --json-out var\agriguard-readiness-browser-smoke-summary-2026-07-06.json --markdown-out var\agriguard-readiness-browser-smoke-summary-2026-07-06.md`
  - Result: exit `1` as expected because readiness remains blocked.
  - Markdown includes `## Browser Smoke Evidence`.
  - Markdown includes `var/agriguard-browser-smoke-suite-compose-launch.json`.
  - Markdown does not include incomplete `None/None` count ratios.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --emit-handoff --status-json-out var\agriguard-guarded-launch-status-browser-smoke-summary-refresh-2026-07-06.json`
  - Result: exit `1` as expected because strict preflight still blocks launch.
  - Readiness JSON includes `reports.launch.browser_smoke.found=false`.
  - Readiness JSON includes `reports.launch.browser_smoke.path=var/agriguard-browser-smoke-suite-compose-launch.json`.
  - Handoff validation remains `pass`; artifact index remains `pass` and `ready`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. The latest checked missing path remains `C:\secure\missing-firebase-service-account.json`.
