# Auto Research Loop - AgriGuard Firebase Path Shape Gate

Date: 2026-07-06

## Source Basis

- OWASP secrets-management guidance supports keeping service-account material outside the repository and validating secret-file handling before launch.
- AgriGuard strict preflight already rejects missing, invalid, or repository-local Firebase service-account files. The earlier shape-only env validator only checked the `.json` suffix, so an operator could pass shape validation with a relative repo-local service-account path and fail later.

## Change

- Tightened `apps/AgriGuard/scripts/validate_launch_env_template.py`.
- `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` now fails shape validation unless it is an absolute `.json` path outside the repository.
- The validator still does not require the file to exist; strict preflight remains responsible for file existence and JSON-content validation.
- Added focused tests for:
  - relative `firebase-service-account.json`
  - absolute repository-local Firebase JSON paths
  - redaction of the rejected repo-local path in validation output

## Verification

- Focused unit check:
  - `python -m pytest apps\AgriGuard\backend\tests\test_validate_launch_env_template.py -q`
  - Result: `7 passed`.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-firebase-path-shape-2026-07-06.json`
  - Result: current operator env validation remains `ready`, and full status remains `blocked` with `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Unsafe Firebase service-account path shapes now fail earlier in the operator env validator. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
