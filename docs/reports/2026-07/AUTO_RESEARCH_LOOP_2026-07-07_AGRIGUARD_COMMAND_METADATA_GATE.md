# AutoResearch Loop - AgriGuard Command Metadata Gate - 2026-07-07

## Objective

Fail closed when guarded-launch handoff consumer metadata contains a stale or incomplete ready-gate command, especially a command missing the selected `--env-file`.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_COMMAND_METADATA_GATE.md`
- `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMMAND_METADATA_GATE_2026-07-07.md`

## Source-Backed Check

- GitHub modernization radar command:
  - `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-command-metadata-gate-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMMAND_METADATA_GATE_2026-07-07.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`
- Latest commit refresh: `checked=8`, `updated=6`, `failed=0`, `review_required=6`
- Veritas AutoResearch source HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: `consumer_command_metadata_status=pass` only required command text presence/counts. A stale ready-gate command without `--env-file` could still pass.
- Variant: require ready-gate command metadata to include `--status-only`, `--require-ready`, `--env-file`, and `--status-json-out`.
- Primary KPI: stale default artifact index with missing `--env-file` must fail with a machine-readable missing flag.
- Guardrail: regenerated current artifacts must still pass once the command includes all required flags.
- Decision: adopt. The variant caught stale command metadata and the recovered current artifact index passed.

## Changes

- Added `READY_GATE_COMMAND_REQUIRED_FLAGS` in `index_guarded_launch_artifacts.py`.
- Added `consumer_ready_gate_command_required_flags` and `consumer_ready_gate_command_missing_flags` to the artifact index JSON.
- Made `consumer_command_metadata_status` fail when required ready-gate command flags are missing.
- Added Markdown output for missing ready-gate command flags.
- Updated passing fixtures to include `--env-file` and added a regression for missing `--env-file`.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - Result: `12 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Result: `56 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-command-metadata-gate.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Baseline check against the stale default guarded-launch artifacts:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-artifact-index-command-metadata-current-2026-07-07.json --markdown-out var\agriguard-guarded-launch-artifact-index-command-metadata-current-2026-07-07.md
```

- Result: exit `1`
- `status=fail`
- `blocker_class=artifact_index_blocked`
- `consumer_command_metadata_status=fail`
- `consumer_ready_gate_command_missing_flags=["--env-file"]`
- `recovery_command_status=pass`

Recovery/regeneration command:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --emit-handoff
```

- Result: exit `1`, expected because strict preflight still fails closed.
- Firebase blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Post-recovery artifact index:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-artifact-index-command-metadata-after-recovery-2026-07-07.json --markdown-out var\agriguard-guarded-launch-artifact-index-command-metadata-after-recovery-2026-07-07.md --exit-zero-on-fail
```

- Result: exit `0`
- `status=pass`
- `blocker_class=ready`
- `consumer_command_metadata_status=pass`
- `consumer_ready_gate_command_missing_flags=[]`
- Ready-gate command includes `--env-file 'D:\AI project\var\agriguard-launch-operator.missing-firebase.env'`
- `operator_action_ids=["set_firebase_service_account_file"]`

## Current Launch State

The artifact index now rejects stale ready-gate command metadata instead of treating it as release-ready evidence. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
