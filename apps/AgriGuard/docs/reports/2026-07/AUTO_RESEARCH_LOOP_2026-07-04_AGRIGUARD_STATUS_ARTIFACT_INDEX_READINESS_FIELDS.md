# AutoResearch Loop - AgriGuard Status Artifact Index Readiness Fields

## Objective

Expose the artifact index's consumer readiness facts in the compact
`run_guarded_launch.py --status-only` view. The raw artifact index already
recorded whether the indexed handoff consumer saw env validation as ready,
which operator action IDs were current, and which preflight status blocked the
packet, but the compact status JSON only surfaced the index status and recovery
state.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: compact status exposes artifact-index existence, status, missing
  roles, packet validation status, and recovery command status only.
- Variant: compact status also exposes
  `consumer_readiness_operator_action_ids`,
  `consumer_readiness_env_validation_ready_for_preflight`,
  `consumer_readiness_env_validation_placeholder_count`, and
  `consumer_readiness_operator_packet_preflight_status`.
- Primary KPI: live `--status-only` output lets an operator compare the current
  readiness summary with the indexed handoff consumer readiness without opening
  the raw artifact-index JSON.
- Guardrails: handoff schema validation, focused wrapper/handoff/index tests,
  and canonical AgriGuard smoke must pass.

## Change

`_build_status_view()` now copies the artifact index's consumer readiness
fields into `status_view.artifact_index`. The guarded-launch handoff schema was
extended so embedded handoff JSON validates with those fields.

## Verification Commands

```powershell
python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py
```

Result: passed.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `18 passed in 0.76s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-status-artifact-index-readiness-fields-20260704.json
```

Result: compact status stayed `blocked` with `blocker_class=preflight_blocked`
and now includes:

- `artifact_index.consumer_readiness_operator_action_ids=["set_firebase_service_account_file"]`
- `artifact_index.consumer_readiness_env_validation_ready_for_preflight=true`
- `artifact_index.consumer_readiness_env_validation_placeholder_count=0`
- `artifact_index.consumer_readiness_operator_packet_preflight_status=fail`

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q
```

Result: `39 passed in 1.78s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-artifact-index-readiness-fields-20260704 --emit-handoff --status-json-out var\agriguard-guarded-launch-artifact-index-readiness-fields-20260704-status.json
```

Result: expected exit code `1` because the template env file remains
`env_shape_blocked`; handoff validation still passed with the expanded schema
and `packet_validation_status=pass`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-artifact-index-readiness-fields-20260704.json
```

Result: `passed=5`, `failed=0`, `total=5`, elapsed `6m48s`.

## Decision

Adopt the variant. Compact status now shows both the current readiness summary
and the indexed handoff consumer readiness facts, making stale or divergent
artifact-index state visible without weakening the launch gate.

## Remaining Blocker

The current default guarded-launch prefix is `preflight_blocked` on
`set_firebase_service_account_file`. A real Firebase Admin service-account JSON
path must be supplied outside the repository before compose/browser launch can
continue.

## Next Cycle

Continue reducing operator ambiguity around the Firebase service-account
preflight blocker, or move to the next product surface with live-click evidence.
