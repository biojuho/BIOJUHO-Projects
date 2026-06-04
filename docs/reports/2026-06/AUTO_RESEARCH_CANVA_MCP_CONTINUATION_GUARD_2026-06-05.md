# AutoResearch Canva MCP Continuation Guard

- Date: 2026-06-05
- Cycle status: adopted as regression guard
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `mastra-ai/mastra` commit digest entry for client tools and
  signal continuation handling.
- Primary source: https://github.com/mastra-ai/mastra

## A/B Contract

- Baseline: Canva MCP already passed continuation tokens through several
  server branches, but the real pre-push pytest bundle did not guard the
  schema, tool descriptions, or server propagation together.
- Variant: add a focused continuation contract test and wire
  `tests/test_canva_mcp_openapi_contract.py` into the real pre-push hook.
- Primary KPI: continuation-capable Canva tools keep their pagination contract
  visible to operators and preserved in server query propagation.
- Guardrails: no Canva product behavior changes, no credentialed API calls, and
  no claim that upstream Mastra code was adopted directly.
- Decision rule: adopt only if the focused Canva/hook suite passes and the
  completion/objective audits keep the global objective open.

## Result

- Adopted variant: yes.
- Continuation tools guarded:
  - `search-designs`
  - `list-folder-items`
  - `list-comments`
  - `list-replies`
- Guarded surfaces:
  - tool descriptions mention continuation
  - JSON schemas expose `continuation`
  - Zod parsers accept optional `continuation`
  - server branches append `continuation` to Canva API query parameters
  - search results preserve `data.continuation` in structured content
- Pre-push wiring: `tests/test_canva_mcp_openapi_contract.py` is now in
  `ops/hooks/pre-push` and asserted by `tests/test_pre_push_hook.py`.

## Changed Paths

- `tests/test_canva_mcp_openapi_contract.py`
- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`
- `tests/test_autoresearch_completion_audit.py`
- `docs/reports/2026-06/AUTO_RESEARCH_CANVA_MCP_CONTINUATION_GUARD_2026-06-05.md`

## Verification

- `python -m pytest tests/test_canva_mcp_openapi_contract.py tests/test_pre_push_hook.py -q`
  - Passed: `12 passed`.
- `python ops/scripts/autoresearch_completion_audit.py --json-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - Passed: `42` criteria, `global_objective_complete=false`.
- `python ops/scripts/autoresearch_objective_coverage.py --json-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - Passed: `7` requirements, `global_objective_complete=false`.

## Next Cycle

- Use the remaining digest signals to choose one local behavior hardening
  target. The strongest follow-up is Agent Framework hosted-agent consent
  evidence against the external credential operator workflow.
