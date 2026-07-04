# AutoResearch Loop - AgriGuard Prepared Env Firebase JSON Shape

Date: 2026-07-04

## Hypothesis

`prepare_launch_env.py` already failed closed when the Firebase Admin service-account path was missing, but it could still mark an existing `{}` JSON file as ready for preflight. Strict launch preflight already validates the Firebase service-account shape, so the prepare step should reuse that same check and fail earlier.

## Changes

- Reused the strict preflight Firebase credential checker in `prepare_launch_env.py`.
- Added local-file check fields:
  - `firebase_service_account_file_exists`
  - `firebase_service_account_file_valid`
  - redacted file path
- Kept `--allow-missing-firebase-file` as planning-only behavior:
  - missing file is allowed only when that flag is set;
  - an existing but invalid file still fails closed.
- Updated `test_prepare_launch_env.py` fixtures to use a service-account-shaped JSON file.
- Added a regression test proving `{}` is rejected with required service-account field errors.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q`
  - 6 passed.
- Real invalid Firebase JSON helper run:
  - input file contained `{}`;
  - exit code `1`;
  - report status `fail`;
  - `firebase_service_account_file_exists=true`;
  - `firebase_service_account_file_valid=false`;
  - blocking findings included missing service-account fields.
- Real valid Firebase-shaped helper run:
  - exit code `0`;
  - report status `pass`;
  - ready for preflight `true`;
  - `firebase_service_account_file_exists=true`;
  - `firebase_service_account_file_valid=true`.
- Workspace smoke:
  - `var/workspace-smoke-agriguard-prepare-env-firebase-json-shape.json`
  - 5/5 AgriGuard checks passed.
- Guarded launch status:
  - `var/agriguard-guarded-launch-status-prepare-env-firebase-json-shape.json`
  - status `blocked`; blocker class `preflight_blocked`;
  - env validation ready for preflight with 0 placeholders;
  - remaining operator action `set_firebase_service_account_file`;
  - remaining preflight error `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Launch Readiness Result

This loop makes the operator env preparation step match strict preflight semantics for Firebase Admin credentials. Local verification is green. The launch path remains blocked only because the real external Firebase Admin service-account JSON has not been provided on this host.
