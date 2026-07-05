# Auto Research Loop - AgriGuard Allow-Missing Firebase Hardening

Date: 2026-07-06

## Source Basis

- OWASP secrets-management guidance supports validating secret-file location and format even when local workflows intentionally skip secret-file existence checks.
- AgriGuard's `--allow-missing-firebase-credentials` mode is useful for local preflight shape checks, but it should suppress only the missing-file error. Unsafe path shape must still fail closed.

## Change

- Tightened `apps/AgriGuard/scripts/launch_env_preflight.py`.
- `allow_missing_firebase_credentials=True` now suppresses only `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- Repository-local paths and non-JSON suffixes remain blocking even when missing-file checks are allowed.
- Added focused tests for:
  - missing repo-local Firebase path
  - missing wrong-suffix Firebase path
  - unchanged ordinary missing-file behavior

## Verification

- Focused preflight checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_launch_env_preflight.py::test_launch_report_allow_missing_firebase_credentials_still_rejects_repo_local_path apps\AgriGuard\backend\tests\test_launch_env_preflight.py::test_launch_report_allow_missing_firebase_credentials_still_rejects_wrong_suffix apps\AgriGuard\backend\tests\test_launch_env_preflight.py::test_launch_report_rejects_missing_compose_firebase_credentials_file -q`
  - Result: `3 passed`.
- Full launch preflight suite:
  - `python -m pytest apps\AgriGuard\backend\tests\test_launch_env_preflight.py -q`
  - Result: `68 passed`.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-allow-missing-firebase-hardening-2026-07-06.json`
  - Result: current operator env validation remains `ready`, and full status remains `blocked` with `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Local missing-file bypasses can no longer hide unsafe Firebase service-account path shape. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
