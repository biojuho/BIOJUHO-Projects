# AutoResearch Loop - AgriGuard Custom Handoff Artifact Index

## Objective

Fix guarded-launch artifact indexing when operators choose custom handoff
output paths. The wrapper could render and validate a custom handoff, but the
artifact index still checked the default handoff filenames and reported missing
required roles.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: keep artifact indexing tied to default handoff filenames.
- Variant: let the indexer accept explicit handoff artifact paths and make the
  guarded-launch wrapper pass the resolved custom paths into the index command.
- Primary KPI: a real guarded-launch run with custom handoff paths should keep
  the external launch blocker, but the artifact index should pass with no
  missing handoff roles.
- Guardrails: focused wrapper/index tests and canonical AgriGuard smoke must
  pass.

## Baseline Evidence

Command:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff --handoff-json-out var\agriguard-guarded-launch-after-browser-runtime.handoff.json --handoff-markdown-out var\agriguard-guarded-launch-after-browser-runtime.handoff.md --handoff-validation-json-out var\agriguard-guarded-launch-after-browser-runtime.handoff.validation.json --handoff-consumer-json-out var\agriguard-guarded-launch-after-browser-runtime.handoff.consumer.json
```

Result: handoff validation passed, but the artifact index failed with missing
required roles for default `handoff_json`, `handoff_markdown`,
`handoff_validation_json`, and `handoff_consumer_json` paths.

## Variant Evidence

- `index_guarded_launch_artifacts.py` now supports `--handoff-json`,
  `--handoff-markdown`, `--handoff-validation-json`,
  `--handoff-consumer-json`, and `--ready-gate-json`.
- `run_guarded_launch.py` passes the resolved handoff paths into the artifact
  index command.
- Recovery commands emitted by the indexer preserve custom handoff path flags
  when an indexed custom run still needs regeneration.
- Added focused tests for direct custom-path indexing and guarded-launch dry-run
  command planning.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `22 passed in 1.05s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff --handoff-json-out var\agriguard-guarded-launch-custom-index.handoff.json --handoff-markdown-out var\agriguard-guarded-launch-custom-index.handoff.md --handoff-validation-json-out var\agriguard-guarded-launch-custom-index.handoff.validation.json --handoff-consumer-json-out var\agriguard-guarded-launch-custom-index.handoff.consumer.json --artifact-index-json-out var\agriguard-guarded-launch-custom-index.artifact-index.json --artifact-index-markdown-out var\agriguard-guarded-launch-custom-index.artifact-index.md
```

Result: process exited `1` because launch remains `env_shape_blocked`, which is
expected without production env values. The artifact index itself passed:
`status=pass`, `missing_required_roles=[]`, `consumer_packet_validation_status=pass`,
`validation_status=pass`, `recovery_command_status=not_required`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-custom-handoff-artifact-index.json
```

Result: `passed=5`, `failed=0`, `total=5`.

## Decision

Adopt the custom handoff artifact-index path propagation. It removes a false
artifact-index failure while preserving the real external launch blocker.

## Next Cycle

Commit and push this scoped patch, then continue with the next launch-readiness
gap.
