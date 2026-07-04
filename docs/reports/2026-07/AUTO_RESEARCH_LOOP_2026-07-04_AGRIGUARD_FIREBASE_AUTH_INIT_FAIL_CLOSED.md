# AutoResearch Loop: AgriGuard Firebase Auth Init Fail-Closed

Date: 2026-07-04

## Objective

Harden AgriGuard launch authentication so a present but invalid Firebase Admin
service-account file cannot crash backend import or startup. The product should
continue to fail closed on protected routes until a real Firebase credential is
provided or an explicit development fallback is enabled.

## Scope and Owned Paths

- `apps/AgriGuard/backend/auth.py`
- `apps/AgriGuard/backend/tests/test_auth_security.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_FIREBASE_AUTH_INIT_FAIL_CLOSED.md`

## External Sources Checked

- Firebase Admin SDK setup: https://firebase.google.com/docs/admin/setup
  - Source basis: Firebase Admin authentication requires a Firebase project,
    service account, and a credential configuration file. For service-account
    auth, Firebase documents `GOOGLE_APPLICATION_CREDENTIALS` or an explicit
    service-account key path.
- Google Cloud IAM service-account key best practices:
  https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys
  - Source basis: service-account keys are sensitive long-lived credentials;
    keys should not be placed in source repositories or temporary locations.
- Google Cloud Workload Identity Federation:
  https://docs.cloud.google.com/iam/docs/workload-identity-federation
  - Source basis: Workload Identity Federation is the safer direction for
    external workloads where a static service-account key can be avoided.
- Veritas AutoResearch source repository:
  https://github.com/Veritas-7/autoresearch-skill-system
  - Observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Workspace radar:
  `var/github-modernization-radar-auto-research-agriguard-auth-2026-07-04.json`
  reported `8 sources, adopted=8, partially_adopted=0, watch=0`.

## A/B Hypothesis and Decision Rule

- Baseline: `auth.py` directly calls `credentials.Certificate(cred_path)` and
  `firebase_admin.initialize_app(cred)` at import time. A malformed or
  encoding-incompatible credential file can raise during import, crashing the
  backend before protected routes can fail closed.
- Variant: catch Firebase Admin credential initialization exceptions, log only
  the exception class, leave `_firebase_initialized=False`, and preserve the
  existing `verify_firebase_token` 503 fail-closed behavior when
  `ALLOW_DEV_AUTH_FALLBACK` is not explicitly enabled.
- Primary KPI: invalid Firebase credential files no longer crash auth module
  import.
- Guardrails: no dev-auth bypass expansion, launch preflight still rejects
  missing/invalid credential configuration, AgriGuard canonical smoke remains
  green, and browser screenshot artifact gates remain green.
- Decision rule: adopt only if the baseline crash is fixed and all auth,
  launch-preflight, workspace smoke, and browser smoke guardrails pass.

## Baseline Evidence

Before the variant, importing `auth` with
`GOOGLE_APPLICATION_CREDENTIALS=var\agriguard-bad-firebase-service-account.json`
and malformed credential content exited nonzero during module import inside
`credentials.Certificate(cred_path)`. On this Windows locale the observed
exception was `UnicodeDecodeError: 'cp949' codec can't decode byte 0xbf in
position 2`.

An incomplete service-account JSON file also exited nonzero before the backend
could reach route-level fail-closed token handling.

## Variant Evidence

`auth.py` now wraps Firebase credential construction and Admin SDK initialization
with exception handling. Any initialization exception prints:

`[WARNING] Firebase service account key could not initialize (<ExceptionClass>). Token verification disabled.`

The credential path and credential content are not logged. The module leaves
`_firebase_initialized=False`, so protected routes keep using the existing
`HTTP_503_SERVICE_UNAVAILABLE` fail-closed behavior unless
`ALLOW_DEV_AUTH_FALLBACK` is deliberately set.

## Verification Commands

- `python -m ruff check apps/AgriGuard/backend/auth.py apps/AgriGuard/backend/tests/test_auth_security.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/backend/auth.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_auth_security.py -q`
  - Result: `9 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_auth_security.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q`
  - Result: `71 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-auth-init-fail-closed.json`
  - Result: `passed=5, failed=0, total=5`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-auth-init-fail-closed.json --output-dir var\agriguard-browser-smoke-suite-auth-init-fail-closed --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshot_artifacts_total=18, screenshot_artifacts_failed=0`
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-auth-init-fail-closed.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`,
    `operator_action_ids=["set_firebase_service_account_file"]`

## Adopt/Reject Decision

Adopted.

The variant fixes the import-crash failure mode while preserving the secure
runtime posture: invalid Firebase configuration does not open a dev bypass and
does not create a false launch-ready state.

## Remaining Blocker

AgriGuard is still not externally launch-ready because the guarded launch status
is blocked by the operator credential action:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

The correct launch path remains: provide a real Firebase service-account file
outside the repository, point `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` or
`GOOGLE_APPLICATION_CREDENTIALS` at it according to the runtime mode, then rerun
strict preflight and guarded launch.

## Next Cycle

After the operator provides the Firebase credential file, rerun:

1. `python apps/AgriGuard/scripts/launch_env_preflight.py`
2. `python apps/AgriGuard/scripts/run_guarded_launch.py`
3. `python apps/AgriGuard/scripts/run_browser_smoke_suite.py`

If those pass, promote the launch evidence bundle as the next release-candidate
artifact.
