# AutoResearch Loop - AgriGuard Status Artifact Index

## Objective

Fix the guarded-launch compact status view after custom handoff artifact
indexing. The previous loop made the custom artifact index pass, but
`run_guarded_launch.py --status-only` still read the stale artifact-index
recovery summary embedded in the operator packet instead of the current
artifact-index JSON.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: keep compact status recovery data sourced only from the operator
  packet.
- Variant: let compact status read the resolved artifact-index JSON directly
  and prefer that recovery summary when the file exists, including custom
  `--artifact-index-json-out` paths.
- Primary KPI: status-only output for the custom artifact index reports
  `artifact_index.found=true` and
  `artifact_index_recovery_summary.required=false` when the index itself
  passed.
- Guardrails: focused wrapper and handoff tests, full backend tests, and
  canonical AgriGuard smoke must pass.

## Baseline Evidence

The custom artifact index at
`var\agriguard-guarded-launch-custom-index.artifact-index.json` reported:

- `status=pass`
- `missing_required_roles=[]`
- `consumer_packet_validation_status=pass`
- `recovery_command_status=not_required`

But the compact status view still showed the packet's stale recovery note:
`required=true`, `status=pass`, and
`Recovery command is present because this artifact index did not meet pass criteria.`

## Variant Evidence

- `_build_status_view()` now accepts an optional `artifact_index_json` path.
- When the artifact-index JSON exists, compact status uses its
  `recovery_summary` over the operator packet's embedded summary.
- Compact status exposes an `artifact_index` object with path, status,
  missing required roles, consumer validation status, and recovery command
  status.
- `run_guarded_launch.py` passes the resolved default or custom artifact index
  path through status-only, `--status-json-out`, and `--require-ready` paths.
- After a full guarded launch with handoff/index post-processing, status JSON is
  regenerated so the final file reflects the current artifact index while still
  writing an initial status file for the indexer's optional `status_json` role.
- Handoff rendering and schema validation now accept the expanded status view
  and reuse the status view's artifact-index recovery summary.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `17 passed in 0.64s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --artifact-index-json-out var\agriguard-guarded-launch-custom-index.artifact-index.json --status-json-out var\agriguard-guarded-launch-status-after-custom-index-direct.json
```

Result: compact status stayed `blocked` with `blocker_class=env_shape_blocked`,
but correctly read the current artifact index:
`artifact_index.found=true`, `artifact_index.status=pass`,
`artifact_index.missing_required_roles=[]`,
`artifact_index_recovery_summary.required=false`, and
`artifact_index_recovery_summary.status=not_required`.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q
```

Result: `32 passed in 1.19s`.

```powershell
python -m pytest tests -q
```

Working directory: `apps\AgriGuard\backend`.

Result: `578 passed, 1 warning in 170.70s`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-artifact-index.json
```

Result: `passed=5`, `failed=0`, `total=5`, elapsed `6m5s`.

## Decision

Adopt the artifact-index-backed status view. It removes a false recovery
warning from the operator status surface while preserving the real external
launch blocker: production env shape is still blocked until the operator
supplies real credentials and production values outside the repo.

## Next Cycle

Commit and push this scoped patch, then continue with the next launch-readiness
gap.
