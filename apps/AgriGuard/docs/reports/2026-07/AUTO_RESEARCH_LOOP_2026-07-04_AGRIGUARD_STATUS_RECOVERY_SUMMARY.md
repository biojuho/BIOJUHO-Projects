# AutoResearch Loop - AgriGuard Status Recovery Summary

Date: 2026-07-04

## Objective

Expose compact artifact-index recovery state in guarded-launch `--status-only`
output so operators who inspect readiness without rendering the full handoff can
still read one grouped recovery object.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_STATUS_RECOVERY_SUMMARY.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system`
  - Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: `--status-only` reports launch, readiness summary, and operator
  packet metadata, but does not surface artifact-index recovery state.
- Variant: status view includes `artifact_index_recovery_summary`, copied from
  the operator packet when available and fail-closed when the packet is missing.
- Primary KPI: live status-only output exposes grouped recovery state for both
  missing-artifact and packet-present prefixes.
- Guardrail: handoff schema validation, guarded-launch suite, and canonical
  AgriGuard smoke must remain green.
- Decision: adopted.

## Variant Evidence

- Missing operator packet status view now returns:
  - `required: true`
  - `action: Generate the guarded launch operator packet so artifact-index recovery status can be read.`
  - `status: null`
  - `note: Artifact index recovery status is unavailable because the operator packet is missing.`
  - `command: null`
- Packet-present status view copies the grouped recovery object from
  `guarded_launch_evidence.artifact_index_readiness_summary.recovery_summary`.
- The embedded handoff `status_view` schema now requires the same grouped object.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q
```

Result: `23 passed in 0.89s`

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q
```

Result: `67 passed in 2.79s`

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-status-recovery-missing --status-only
python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-packet-recovery-summary --status-only
```

Result:

- missing prefix: `artifact_index_recovery_summary.required=True`, `status=null`, `command=null`
- packet-present prefix: `artifact_index_recovery_summary.required=True`, `status=null`, `command` present

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-recovery-summary.json
```

Result: `passed=5 failed=0 total=5`

Backend test tail in smoke JSON: `570 passed, 2 warnings in 269.54s (0:04:29)`

## Commit and Push Status

Prepared for explicit staging, commit, and push after this report is written.

## Next Cycle

Move from recovery-state consistency to user-facing AgriGuard release readiness:
refresh the supply-chain/browser smoke evidence or QR verification path, then
record the remaining launch blockers separately from local code readiness.
