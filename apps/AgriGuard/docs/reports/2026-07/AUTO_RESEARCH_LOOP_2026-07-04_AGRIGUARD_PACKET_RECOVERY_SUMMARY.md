# AutoResearch Loop - AgriGuard Packet Recovery Summary

Date: 2026-07-04

## Objective

Propagate the grouped artifact-index recovery contract from the operator packet
through the guarded-launch handoff and final consumer view, so every downstream
launch gate can inspect one stable `artifact_index_recovery_summary` object.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_PACKET_RECOVERY_SUMMARY.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system`
  - Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: operator packet, handoff packet validation, and consumer view expose
  flat recovery status/note fields, forcing downstream tools to infer whether a
  recovery command is required.
- Variant: all three layers expose a grouped recovery summary with
  `required`, `action`, `status`, `note`, and `command`, while retaining the
  legacy flat fields.
- Primary KPI: packet -> handoff -> consumer live chain carries the grouped
  object at every layer.
- Guardrail: handoff schema validation, focused packet/handoff/consumer tests,
  guarded-launch suite, and canonical AgriGuard smoke must stay green.
- Decision: adopted.

## Variant Evidence

- `render_launch_operator_packet.py` now mirrors `recovery_summary` from an
  existing artifact index, falls back from legacy top-level fields, and emits a
  missing-index grouped recovery summary.
- `render_guarded_launch_handoff.py` now includes
  `artifact_index_recovery_summary` in `packet_validation` and validates it via
  `guarded_launch_handoff.schema.json`.
- `consume_guarded_launch_handoff.py` now mirrors the grouped object as
  `packet_artifact_index_recovery_summary`.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q
```

Result: `25 passed in 1.42s`

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q
```

Result: `67 passed in 2.79s`

```powershell
python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\missing-preflight-for-packet-recovery-summary.json --json-out var\agriguard-guarded-launch-packet-recovery-summary-operator-packet.json --markdown-out var\agriguard-guarded-launch-packet-recovery-summary-operator-packet.md --env-template-out var\agriguard-guarded-launch-packet-recovery-summary.env.template --exit-zero-on-blocked
python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --output-dir var --output-prefix agriguard-guarded-launch-packet-recovery-summary --ready-gate-json var\agriguard-guarded-launch-packet-recovery-summary-ready-gate.json --json-out var\agriguard-guarded-launch-packet-recovery-summary-handoff.json --markdown-out var\agriguard-guarded-launch-packet-recovery-summary-handoff.md --validation-json-out var\agriguard-guarded-launch-packet-recovery-summary-handoff.validation.json --exit-zero-on-blocked
python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var\agriguard-guarded-launch-packet-recovery-summary-handoff.json --validation-json var\agriguard-guarded-launch-packet-recovery-summary-handoff.validation.json --json-out var\agriguard-guarded-launch-packet-recovery-summary-handoff.consumer.json --exit-zero-on-blocked
```

Result:

- packet `recovery_summary.required=True`
- handoff `artifact_index_recovery_summary.required=True`
- consumer `packet_artifact_index_recovery_summary.required=True`
- consumer recovery command present
- handoff validation status `pass`

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-packet-recovery-summary.json
```

Result: `passed=5 failed=0 total=5`

Backend test tail in smoke JSON: `570 passed, 2 warnings in 275.48s (0:04:35)`

## Commit and Push Status

Prepared for explicit staging, commit, and push after this report is written.

## Next Cycle

Check whether the guarded-launch status-only view should expose a compact
recovery summary for operators who inspect readiness without rendering the full
handoff packet.
