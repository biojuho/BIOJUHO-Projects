# Auto Research Loop - AgriGuard Handoff Browser Smoke Evidence - 2026-07-06

## Objective

Surface the readiness browser-smoke evidence directly in the guarded status view and handoff markdown. The previous loop added `reports.launch.browser_smoke` to the readiness summary; this loop makes that safe subset visible to operators using `run_guarded_launch.py --status-only` or the guarded-launch handoff.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_HANDOFF_BROWSER_SMOKE_EVIDENCE_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Adds `readiness_summary.browser_smoke` to the compact status view.
  - Normalizes missing browser-smoke evidence to a redacted, schema-stable object.
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - Renders a `Status Browser Smoke Evidence` table in handoff markdown when a browser-smoke path, status, or count exists.
  - Avoids incomplete `None/None` count ratios when preflight blocks before browser smoke runs.
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - Adds the strict schema for `status_view.readiness_summary.browser_smoke`.
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Verifies status-only output carries completed browser-smoke evidence.
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - Verifies blocked handoffs render the pending browser-smoke path.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py`
  - Result: `36 passed in 1.88s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --emit-handoff --status-json-out var\agriguard-guarded-launch-status-browser-smoke-handoff-refresh-2026-07-06.json`
  - Result: exit `1` as expected because strict preflight still blocks launch.
  - Status view: `status=blocked`, `blocker_class=preflight_blocked`.
  - Status view: `readiness_summary.browser_smoke.found=false`.
  - Status view: `readiness_summary.browser_smoke.path=var/agriguard-browser-smoke-suite-compose-launch.json`.
  - Handoff JSON validates with `validation_status=pass`.
  - Handoff markdown includes `## Status Browser Smoke Evidence`.
  - Handoff markdown does not include incomplete `None/None` count ratios.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. The latest checked missing path remains `C:\secure\missing-firebase-service-account.json`.
