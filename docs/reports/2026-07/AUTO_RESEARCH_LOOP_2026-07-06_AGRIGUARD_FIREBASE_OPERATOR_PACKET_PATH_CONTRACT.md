# Auto Research Loop - AgriGuard Firebase Operator Packet Path Contract

Date: 2026-07-06

## Local Basis

- `validate_launch_env_template.py` now rejects `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` unless it is an absolute `.json` path outside the repository.
- Strict preflight still owns the existence and Firebase service-account JSON-content checks.
- The operator packet action still described only a host JSON path outside the repo, so the human handoff did not fully mirror the stricter env-shape gate.

## Change

- Tightened `apps/AgriGuard/scripts/render_launch_operator_packet.py`.
- The `set_firebase_service_account_file` action now tells the operator to use an absolute host path for a Firebase Admin service-account `.json` file outside the repo.
- The validation text now tells the operator to pass env-template shape validation first, then strict preflight with `firebase_credentials_file_exists=true` and `firebase_credentials_file_valid=true`.
- The generated operator env template comment now repeats the absolute host path and outside-repo requirements.

## Verification

- Focused unit check:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Result: `17 passed`.
- Operator packet artifact refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --app-root apps/AgriGuard --preflight-json var/agriguard-guarded-launch-preflight.json --json-out var/agriguard-guarded-launch-operator-packet.json --markdown-out var/agriguard-guarded-launch-operator-packet.md --env-template-out var/agriguard-guarded-launch.env.template --env-file var/agriguard-launch-operator.missing-firebase.env --env-validation-json var/agriguard-guarded-launch-env-validation.json --env-validation-markdown var/agriguard-guarded-launch-env-validation.md --compose-launch-report-json var/agriguard-guarded-launch-launch-report.json --readiness-summary-json var/agriguard-guarded-launch-readiness-summary.json --readiness-summary-markdown var/agriguard-guarded-launch-readiness-summary.md --guarded-output-dir var --guarded-output-prefix agriguard-guarded-launch --guarded-status-json var/agriguard-guarded-launch-status.json --guarded-handoff-json var/agriguard-guarded-launch-handoff.json --guarded-handoff-markdown var/agriguard-guarded-launch-handoff.md --guarded-handoff-validation-json var/agriguard-guarded-launch-handoff.validation.json --guarded-handoff-consumer-json var/agriguard-guarded-launch-handoff.consumer.json --guarded-ready-gate-json var/agriguard-guarded-launch-ready-gate.json`
  - Result: wrote refreshed packet JSON, packet Markdown, and env template; exited `1` because the current launch remains blocked.
- Refreshed artifact content:
  - `set_firebase_service_account_file` action now says: `Set this to an absolute host path for a Firebase Admin service account .json file that exists outside the repo.`
  - Env template now says: `# Absolute host path to a Firebase Admin service account .json file outside the repo.`
- Guarded launch status refresh:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-auto-research-continue-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`, `secrets_redacted=true`.

## Current Launch Blocker

The operator handoff now mirrors the stricter Firebase credential path contract. Full guarded launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` file at an absolute host path outside the repository.
