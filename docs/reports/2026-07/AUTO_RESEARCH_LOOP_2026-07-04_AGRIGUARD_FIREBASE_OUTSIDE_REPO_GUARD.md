# AutoResearch Loop: AgriGuard Firebase Outside-Repo Guard

Date: 2026-07-04

## Objective

Make the existing AgriGuard operator instruction enforceable: Firebase Admin
service-account JSON files must live outside the Git repository before launch
preflight can pass.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_prepare_launch_env.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_FIREBASE_OUTSIDE_REPO_GUARD.md`

## External Sources Checked

- Firebase Admin SDK setup: https://firebase.google.com/docs/admin/setup
  - Source basis: Firebase Admin credentials are service-account credentials
    used by server-side code.
- Google Cloud IAM service-account key best practices:
  https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys
  - Source basis: service-account keys are sensitive long-lived credentials and
    should not be checked into source repositories.
- Veritas AutoResearch source repository:
  https://github.com/Veritas-7/autoresearch-skill-system
  - Observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: operator packet and handoff text say
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` should point outside the repo, but
  strict preflight only enforced existence and Firebase JSON shape. A real key
  placed under the repository could pass the file-shape check.
- Variant: strict preflight discovers the nearest `.git` root from `app_root`
  and rejects Firebase service-account paths inside that repository.
- Primary KPI: a valid Firebase service-account JSON inside a repository fails
  strict preflight with a clear error.
- Guardrails: valid Firebase service-account JSON outside the repository still
  passes, operator-env preparation remains usable, canonical AgriGuard smoke
  remains green, and browser screenshot gates remain green.
- Decision rule: adopt only if the repo-local credential case fails, the
  outside-repo case passes, and all launch/env/browser guardrails pass.

## Variant Evidence

The validator now resolves absolute and app-relative Firebase credential paths,
finds the repository root by walking up to `.git`, and appends this launch error
when the credential path is repo-local:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE must point to a Firebase service account file outside the repository.`

The test suite covers both sides with a fake repository:

- repo-local valid Firebase JSON: expected fail
- outside-repo valid Firebase JSON: expected pass

Pass-path tests that use pytest temp credentials now deliberately place fake
credentials outside the detected Git root, matching the operator contract.

## Verification Commands

- `python -m ruff check apps/AgriGuard/scripts/launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py::test_prepare_launch_env_generates_secrets_and_redacted_report -q`
  - Result: `1 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q`
  - Result: `70 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-firebase-outside-repo-guard.json`
  - Result: `passed=5, failed=0, total=5`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-firebase-outside-repo-guard.json --output-dir var\agriguard-browser-smoke-suite-firebase-outside-repo-guard --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshot_artifacts_total=18, screenshot_artifacts_failed=0`
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-firebase-outside-repo-guard.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`,
    `operator_action_ids=["set_firebase_service_account_file"]`

## Adopt/Reject Decision

Adopted.

The variant closes a launch secret-hygiene gap without changing development
auth semantics or weakening the current fail-closed launch gate.

## Remaining Blocker

AgriGuard is still externally blocked by the same operator action:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

When the operator provides the real Firebase service-account file, it must be a
valid JSON service-account file outside the Git repository.

## Next Cycle

After a real outside-repo Firebase credential path is provided, rerun strict
preflight and guarded launch. If preflight passes, continue into compose startup
and authenticated browser smoke with the same screenshot artifact gate.
