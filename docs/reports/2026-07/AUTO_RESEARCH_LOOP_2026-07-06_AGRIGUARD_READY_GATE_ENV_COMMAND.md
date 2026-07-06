# AutoResearch Loop - AgriGuard Ready Gate Env Command - 2026-07-06

## Objective

Ensure guarded-launch handoff and artifact-index ready-gate commands are self-contained by embedding the selected operator env file in copied `run_guarded_launch.py --status-only --require-ready` commands.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `a72f83aa766ed588c43436090ecabc0945ab8b7b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_ENV_COMMAND_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - Adds `--env-file` to the handoff renderer CLI.
  - Threads the env file into both `inspect_status` and `require_ready` operator commands.
  - Uses the guarded-launch default env file when rendering handoffs directly.
- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Passes the selected guarded-launch env file into the handoff renderer command.
- Tests now assert the handoff renderer and wrapper dry-run preserve `--env-file` in ready-gate command metadata.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Result: `54 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-ready-gate-env-command.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Guarded-launch handoff generation:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch-env-command --emit-handoff --status-json-out var\agriguard-guarded-launch-env-command-status-2026-07-06.json --handoff-json-out var\agriguard-guarded-launch-env-command-handoff-2026-07-06.json --handoff-markdown-out var\agriguard-guarded-launch-env-command-handoff-2026-07-06.md --handoff-validation-json-out var\agriguard-guarded-launch-env-command-handoff-validation-2026-07-06.json --handoff-consumer-json-out var\agriguard-guarded-launch-env-command-handoff-consumer-2026-07-06.json --handoff-ready-gate-json-out var\agriguard-guarded-launch-env-command-ready-gate-2026-07-06.json
```

- Result: exit `1`, expected because strict preflight still fails closed before compose.
- Preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- Handoff JSON: `status=blocked`, `blocker_class=preflight_blocked`.
- Handoff consumer JSON: `validation_status=pass`, `consumer_command_metadata_status=pass`, `operator_action_ids=["set_firebase_service_account_file"]`.
- Artifact index JSON: `status=pass`, `blocker_class=ready`, `consumer_command_metadata_status=pass`.
- Ready-gate command metadata now includes `--env-file 'D:\AI project\var\agriguard-launch-operator.missing-firebase.env'`.

## Current Launch State

Operator command metadata is now reproducible for the selected env file. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
