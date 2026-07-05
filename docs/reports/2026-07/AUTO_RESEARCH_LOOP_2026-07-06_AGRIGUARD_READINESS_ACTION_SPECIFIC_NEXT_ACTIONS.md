# Auto Research Loop - AgriGuard Readiness Action-Specific Next Actions

Date: 2026-07-06

## Local Basis

- Current guarded-launch status has exactly one active operator action: `set_firebase_service_account_file`.
- The readiness summary `next_actions` used a generic instruction to provide external launch credentials and paths.
- The operator packet and handoff now describe the Firebase service-account path more precisely, so the readiness summary needed to match that contract.

## Change

- Updated `apps/AgriGuard/scripts/summarize_launch_readiness.py`.
- `next_actions` for preflight/operator-value blockers now derive action-specific text from `operator_action_ids`.
- Firebase-only readiness summaries now tell the operator to provide a real Firebase Admin service-account `.json` at an absolute host path outside the repo for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
- Unknown action IDs still fall back to an explicit listed-action-ID instruction.

## Verification

- Focused summarizer tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Result: `6 passed`.
- Live readiness summary refresh:
  - `python apps/AgriGuard/scripts/summarize_launch_readiness.py --app-root apps/AgriGuard --launch-report-json var/agriguard-guarded-launch-launch-report.json --env-validation-json var/agriguard-guarded-launch-env-validation.json --operator-packet-json var/agriguard-guarded-launch-operator-packet.json --json-out var/agriguard-guarded-launch-readiness-summary.json --markdown-out var/agriguard-guarded-launch-readiness-summary.md --exit-zero-on-blocked`
  - Result: wrote refreshed readiness JSON and Markdown.
- Downstream handoff, consumer, and index refresh:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --app-root apps/AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --ready-gate-json var/agriguard-guarded-launch-ready-gate.json --json-out var/agriguard-guarded-launch-handoff.json --markdown-out var/agriguard-guarded-launch-handoff.md --validation-json-out var/agriguard-guarded-launch-handoff.validation.json --exit-zero-on-blocked`
  - `python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var/agriguard-guarded-launch-handoff.json --json-out var/agriguard-guarded-launch-handoff.consumer.json --exit-zero-on-blocked`
  - `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --app-root apps/AgriGuard --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --status-json var/agriguard-guarded-launch-status.json --handoff-json var/agriguard-guarded-launch-handoff.json --handoff-markdown var/agriguard-guarded-launch-handoff.md --handoff-validation-json var/agriguard-guarded-launch-handoff.validation.json --handoff-consumer-json var/agriguard-guarded-launch-handoff.consumer.json --ready-gate-json var/agriguard-guarded-launch-ready-gate.json --json-out var/agriguard-guarded-launch-artifact-index.json --markdown-out var/agriguard-guarded-launch-artifact-index.md`
  - Result: handoff valid, consumer `errors=[]`, artifact index `status=pass`.
- Broader launch-compose check:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Result: `24 passed`.
- Guarded status refresh:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-readiness-actions-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`; readiness `next_actions` now names only the Firebase service-account path requirement.

## Current Launch Blocker

Operator-facing readiness guidance is now action-specific across packet, handoff, and summary artifacts. Full guarded launch remains externally blocked until the operator supplies the real Firebase Admin service-account `.json` at an absolute host path outside the repository.
