# Auto Research Loop - AgriGuard Status Preflight Checks - 2026-07-06

## Objective

Expose safe operator-packet preflight checks in the guarded launch status-only JSON so dashboard and automation consumers can see the resolved Firebase credential path without opening the full packet artifact.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_PREFLIGHT_CHECKS_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Adds `operator_packet.preflight_checks` to the status-only view.
  - Limits the summary to non-secret launch diagnostics: runtime, Docker check flag, Firebase credential source and resolved path, forbidden launch flags, origin/public URL sources, and database source fields.
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - Allows the same safe preflight-check subset inside `status_view.operator_packet`.
  - Keeps the field optional so older handoff artifacts remain schema-compatible.
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Verifies status-only output includes the Firebase credential source and resolved path.
- `apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py`
  - Verifies handoff validation accepts the new status-view preflight-check object.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py`
  - Result: `32 passed in 1.10s`
- `python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-guarded-launch-handoff.json --json-out var\agriguard-guarded-launch-handoff.validation.status-preflight-checks-before-refresh.json`
  - Result: validation passed after schema update.
- Guarded refresh and status-only proof:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --emit-handoff --status-json-out var\agriguard-guarded-launch-status-status-preflight-checks-refresh2-2026-07-06.json`
  - Result: exit `1` as expected because strict preflight blocks launch.
  - Handoff validation status: `pass`, blocker class: `ready`
  - Post-refresh status-only status: `blocked`, blocker class: `preflight_blocked`
  - Artifact index status: `pass`, blocker class: `ready`
  - `operator_packet.preflight_checks.firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`
  - Error remains fail-closed: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
