# AutoResearch Loop - AgriGuard Dry-Run Recovery Summary

Date: 2026-07-04

## Objective

Make the guarded-launch dry-run readiness payload expose the same grouped
`recovery_summary` contract as the artifact index so operators and downstream
consumers do not need to reconstruct recovery intent from scattered top-level
fields.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_DRY_RUN_RECOVERY_SUMMARY.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system`
  - Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: dry-run `artifact_index_readiness_summary` exposes legacy
  top-level recovery fields but not the grouped `recovery_summary` contract.
- Variant: dry-run payload copies `recovery_summary` from an existing artifact
  index and emits a same-shaped missing-index fallback with the recovery command.
- Primary KPI: downstream dry-run consumers can read one stable grouped
  recovery object for both existing-index and missing-index states.
- Guardrail: existing dry-run command shape, missing-index command semantics,
  and guarded-launch tests must remain green.
- Decision: adopted. The variant preserves legacy fields and adds grouped
  recovery data without regressing focused tests, guarded-launch tests, live
  dry-run behavior, or canonical AgriGuard smoke.

## Baseline Evidence

- `run_guarded_launch._artifact_index_readiness_summary` exposed
  `recovery_command_status`, `recovery_command_note`, `missing_index_action`,
  and `missing_index_command`, but did not include `recovery_summary`.

## Variant Evidence

- Existing artifact index case now copies `recovery_summary` when present.
- Legacy artifact index case now builds a compatible grouped fallback from
  `recovery_action`, `recovery_command`, `recovery_command_status`, and
  `recovery_command_note`.
- Missing artifact index case now emits:
  - `required: true`
  - `action: Run the guarded launch wrapper without --dry-run to generate the artifact index evidence.`
  - `status: null`
  - `note: Artifact index recovery status is resolved after the guarded wrapper emits the artifact index.`
  - `command: <wrapper command without --dry-run>`

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `15 passed in 0.69s`

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q
```

Result: `67 passed in 2.64s`

```powershell
$json = python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-dry-run-recovery-summary --emit-handoff --dry-run | ConvertFrom-Json
$s = $json.artifact_index_readiness_summary.recovery_summary
```

Result:

- `required=True`
- `status=null`
- `command` present
- `--dry-run` absent from recovery command
- `--emit-handoff` present in recovery command

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dry-run-recovery-summary.json
```

Result: `passed=5 failed=0 total=5`

Backend test tail in smoke JSON: `570 passed, 2 warnings in 316.94s (0:05:16)`

## Commit and Push Status

Prepared for explicit staging, commit, and push after this report is written.

## Next Cycle

Continue reducing operator ambiguity in guarded-launch handoff outputs by
checking whether the consumer packet and ready-gate summaries should also expose
the grouped recovery object directly.
