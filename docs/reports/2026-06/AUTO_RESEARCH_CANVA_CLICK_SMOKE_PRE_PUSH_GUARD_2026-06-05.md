# Canva Click Smoke Pre-Push Guard

- Date: 2026-06-05
- Scope: pre-push regression gate for the Canva widget click-smoke script
- Baseline: `tests/test_canva_widget_click_smoke.py` existed and the product proof was recorded, but the real pre-push pytest bundle did not directly include the new click-smoke regression tests.
- Variant: add `tests/test_canva_widget_click_smoke.py` to `ops/hooks/pre-push` and assert the hook includes it.
- Primary KPI: the push gate catches regressions in the Canva click-smoke reporter before future AutoResearch commits are pushed.
- Guardrails: hook installer check remains read-only; existing credential, MCP runtime, browser smoke, completion audit, and objective coverage gates remain in place.

## Adopted Variant

Adopted. The pre-push pytest bundle now includes `tests/test_canva_widget_click_smoke.py`, and `tests/test_pre_push_hook.py` asserts that the hook keeps it.

## Changed Paths

- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`
- `ops/references/autoresearch_completion_contract.json`

## Verification

- `python -m pytest tests\test_pre_push_hook.py tests\test_canva_widget_click_smoke.py -q` -> `10 passed`
- `python ops\scripts\autoresearch_completion_audit.py` -> `38` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py` -> `7` requirements, `cycle_prompt_covered=true`, `global_objective_complete=false`

## Remaining Boundary

This strengthens local regression protection for the Canva widget click-smoke tooling. It does not complete credential-gated live Canva OAuth/OpenAPI execution.

global_objective_complete=false
