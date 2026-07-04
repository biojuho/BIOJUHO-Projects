# AutoResearch Loop 2026-07-04 AgriGuard Handoff Consumer Packet Validation

## Objective

Propagate handoff `packet_validation` status into the compact consumer view and fail closed when packet evidence validation drifts.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_HANDOFF_CONSUMER_PACKET_VALIDATION.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the compact handoff consumer checks schema and validation freshness, but it does not expose or enforce packet evidence validation health.
- Variant: add packet validation fields to the consumer view and append a consumer error when `packet_validation.status` is not `pass`.
- Primary KPI: live consumer view reports `packet_validation_status=pass`, evidence outputs `pass`, Markdown table `pass`, zero path mismatches, and no errors while preserving blocked handoff status.
- Guardrails: no README edits, no secret values, no launch execution changes, and `--exit-zero-on-blocked` must still fail when validation errors exist.

## Variant Evidence

- Focused consumer/handoff tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q`
  - Result: `13 passed in 0.99s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `59 passed in 2.07s`
- Live consumer refresh:
  - `python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var\agriguard-guarded-launch-wrapper-emit-index-filled-handoff-packet-validation.json --validation-json var\agriguard-guarded-launch-wrapper-emit-index-filled-handoff-packet-validation.validation.json --json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-handoff-packet-validation.consumer.json --exit-zero-on-blocked`
  - Result: exit code `0`, `status=fail`, `handoff_status=blocked`, `ready_gate_status=fail`, `validation_status=pass`, `validation_matches_handoff=true`, `packet_validation_status=pass`, `packet_evidence_outputs_status=pass`, `packet_markdown_table_status=pass`, `packet_path_mismatch_count=0`, `errors=[]`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-consumer-packet-validation.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `562 passed, 2 warnings`.

## Decision

Adopt the variant. The compact handoff consumer now exposes packet validation health and refuses clean blocked handling when packet evidence validation is not passing.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Wire the guarded-launch artifact index to record packet-validation consumer fields so release artifact reviews can see whether blocked evidence is clean or structurally unsafe.
