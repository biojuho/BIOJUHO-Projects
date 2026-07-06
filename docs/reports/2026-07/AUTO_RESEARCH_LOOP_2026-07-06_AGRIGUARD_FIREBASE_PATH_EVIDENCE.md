# Auto Research Loop - AgriGuard Firebase Path Evidence - 2026-07-06

## Objective

Carry the exact resolved Firebase Admin service-account path through the strict launch preflight and operator packet so the remaining launch blocker is directly actionable, not just reported as a generic missing file.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_FIREBASE_PATH_EVIDENCE_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/launch_env_preflight.py`
  - Adds `checks.firebase_credentials_resolved_path` for file-backed Firebase credential sources.
  - Uses the same resolved app root for the visible path and the existing Firebase credential file validator.
  - Sets the field to `null` when no file-backed Firebase source is selected.
- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - Carries `firebase_credentials_resolved_path` into `preflight_checks` so the operator packet shows the exact host path being checked.
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Covers accepted outside-repository Firebase service-account files and missing compose Firebase files.
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Verifies the resolved missing path survives packet rendering and remains redacted-safe.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Result: `85 passed in 1.42s`
- `python apps/AgriGuard/scripts/launch_env_preflight.py --check-docker --json-out var\agriguard-firebase-path-evidence-preflight.json --env-file var\agriguard-launch-operator.missing-firebase.env`
  - Result: exit `1`, `status=fail`, `blocker_class=preflight_blocked`
  - `checks.firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`
  - Error remains fail-closed: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- `python apps/AgriGuard/scripts/render_launch_operator_packet.py --app-root apps\AgriGuard --preflight-json var\agriguard-firebase-path-evidence-preflight.json --json-out var\agriguard-firebase-path-evidence-operator-packet.json --markdown-out var\agriguard-firebase-path-evidence-operator-packet.md --env-template-out var\agriguard-firebase-path-evidence.env.template`
  - Result: exit `1`, `status=blocked`, `blocker_class=operator_values_required`
  - `preflight_checks.firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-firebase-path-evidence-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Local artifact index and consumer metadata remain `pass`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
