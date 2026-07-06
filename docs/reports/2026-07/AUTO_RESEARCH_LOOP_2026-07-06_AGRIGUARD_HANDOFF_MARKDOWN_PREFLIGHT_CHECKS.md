# Auto Research Loop - AgriGuard Handoff Markdown Preflight Checks - 2026-07-06

## Objective

Expose safe status preflight checks in the top-level guarded launch handoff markdown so the resolved Firebase credential path is visible in the human handoff document, not only in JSON artifacts.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_HANDOFF_MARKDOWN_PREFLIGHT_CHECKS_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - Adds a conditional `Status Preflight Checks` markdown section when the embedded status view includes preflight checks.
  - Renders the same safe status values already exposed in JSON, including `firebase_credentials_resolved_path`.
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - Extends the blocked preflight fixture with Firebase preflight checks.
  - Verifies the resolved Firebase path appears in the handoff markdown table.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - Result: `4 passed in 0.46s`
- `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-handoff-status-preflight-checks.json --markdown-out var\agriguard-guarded-launch-handoff-status-preflight-checks.md --validation-json-out var\agriguard-guarded-launch-handoff-status-preflight-checks.validation.json`
  - Result: exit `1` as expected because the selected handoff remains blocked.
  - Validation status: `pass`
  - Markdown includes `## Status Preflight Checks`.
  - Markdown includes `firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-handoff-markdown-preflight-checks-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Local artifact index remains `pass` and `ready`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
