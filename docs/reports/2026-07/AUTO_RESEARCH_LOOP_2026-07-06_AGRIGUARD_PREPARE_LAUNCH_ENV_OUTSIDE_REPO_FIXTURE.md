# AutoResearch Loop: AgriGuard Prepare Launch Env Outside-Repo Fixture

Date: 2026-07-06

## Change

- Kept the production Firebase service-account path guard strict: launch preflight still requires an absolute `.json` path outside the repository.
- Refactored `test_prepare_launch_env.py` to use a shared outside-repo secret root helper.
- Updated the two missing-Firebase planning fixtures to point at an outside-repo, still-missing `.json` path when `--allow-missing-firebase-file` is used.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py::test_prepare_launch_env_safe_next_commands_can_target_guarded_bundle apps/AgriGuard/backend/tests/test_prepare_launch_env.py::test_prepare_launch_env_can_allow_missing_firebase_file_for_planning -q`
  - Result: `2 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q`
  - Result: `7 passed`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-post-prepare-launch-env-fixture.json`
  - Result: `passed=5, failed=0, total=5`

## Evidence

- Previous canonical smoke artifact `var/workspace-smoke-agriguard-2026-07-06-post-e2e-strict-port.json` failed only `agriguard backend tests`.
- The failed backend tests were:
  - `tests/test_prepare_launch_env.py::test_prepare_launch_env_safe_next_commands_can_target_guarded_bundle`
  - `tests/test_prepare_launch_env.py::test_prepare_launch_env_can_allow_missing_firebase_file_for_planning`
- The direct failure mode was a repo-local pytest temp path violating the outside-repo Firebase service-account path shape rule.
- The passing smoke rerun wrote `var/workspace-smoke-agriguard-2026-07-06-post-prepare-launch-env-fixture.json`.

## Remaining External Blocker

Real compose/browser launch remains blocked until the operator provides a real Firebase Admin service-account `.json` at an absolute host path outside the repo for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
