# Auto Research Loop - AgriGuard Handoff Action-Aware Blocker Summary

Date: 2026-07-06

## Local Basis

- Current guarded-launch status has exactly one active operator action: `set_firebase_service_account_file`.
- The handoff `external_blocker.summary` was static and still mentioned secret, pepper, public verify URL, allowed origin, and database credential work even when those were not active blockers.
- That made the handoff less precise than the operator packet, readiness summary, and status view.

## Change

- Replaced the static handoff external-blocker summary in `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`.
- The summary now derives from `operator_action_ids`.
- Firebase-only handoffs now state only the missing absolute outside-repo Firebase Admin service-account `.json`.
- Env-shape and other known action IDs now render action-specific requirements; unknown action IDs fall back to a generic listed-actions summary.

## Verification

- Focused handoff tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - Result: `4 passed`.
- Handoff renderer plus schema validation:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --app-root apps/AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --ready-gate-json var/agriguard-guarded-launch-ready-gate.json --json-out var/agriguard-guarded-launch-handoff.json --markdown-out var/agriguard-guarded-launch-handoff.md --validation-json-out var/agriguard-guarded-launch-handoff.validation.json --exit-zero-on-blocked`
  - Result: `AgriGuard guarded-launch handoff valid`.
- Handoff consumer refresh:
  - `python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var/agriguard-guarded-launch-handoff.json --json-out var/agriguard-guarded-launch-handoff.consumer.json --exit-zero-on-blocked`
  - Result: `errors=[]`, `external_blocker_summary` names only the Firebase service-account path requirement.
- Artifact index refresh:
  - `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --app-root apps/AgriGuard --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --status-json var/agriguard-guarded-launch-status.json --handoff-json var/agriguard-guarded-launch-handoff.json --handoff-markdown var/agriguard-guarded-launch-handoff.md --handoff-validation-json var/agriguard-guarded-launch-handoff.validation.json --handoff-consumer-json var/agriguard-guarded-launch-handoff.consumer.json --ready-gate-json var/agriguard-guarded-launch-ready-gate.json --json-out var/agriguard-guarded-launch-artifact-index.json --markdown-out var/agriguard-guarded-launch-artifact-index.md`
  - Result: `status=pass`, `consumer_validation_matches_handoff=true`, `consumer_command_metadata_status=pass`.
- Downstream consumer regression check:
  - `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - Result: `13 passed`.
- Guarded status refresh:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-handoff-summary-indexed-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

The handoff no longer overstates unrelated credential work. Full guarded launch remains externally blocked until an operator supplies the real Firebase Admin service-account `.json` at an absolute host path outside the repository.
