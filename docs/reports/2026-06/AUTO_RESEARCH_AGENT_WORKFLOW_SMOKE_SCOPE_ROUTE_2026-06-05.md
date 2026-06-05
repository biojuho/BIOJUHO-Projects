# AutoResearch Agent Workflow Smoke-Scope Route Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Source signal: `crewAIInc/crewAI` commit `906cd97`, `feat(flow): type DSL triggers as route-aware decorators (#6042)`.
- Source link: https://github.com/crewAIInc/crewAI/commit/906cd9769d7e2125485bbc09e8d8ef5cb1c29805

## A/B Contract

- Baseline: `agent_workflow_gate_runner.py` could plan or execute one workflow
  by id or every declared workflow. Operators could not route the gate matrix
  by the manifest's existing `smoke_scope`, so MCP-only launch checks required
  either manual workflow ids or a broader all-workflow plan.
- Variant: add `--smoke-scope` as a route-aware matrix selector. It reuses the
  existing manifest field, rejects ambiguous selectors, writes
  `requested_smoke_scope`, and keeps `--gate-index` limited to single-workflow
  runs.
- Primary KPI: the MCP route matrix selects exactly the two `mcp` workflows and
  no unrelated workflow rows.
- Guardrails: `--workflow` and `--all-workflows` behavior remains unchanged;
  side-effecting gates still require `--allow-side-effect-gates`; the default
  mode remains dry-run planning.
- Decision rule: adopt only if runner tests pass, the script compiles, the
  routed dry-run artifact is valid, and AutoResearch audits remain green.

## Result

- Adopted variant: yes.
- `--smoke-scope mcp --max-gates 1` generated a dry-run matrix with
  `workflows=2`, `selected=2`, and `planned=2`.
- Selected workflows: `dailynews-x-ops` and `canva-widget-oauth-preview`.
- Non-MCP workflows such as `workspace-quality-dashboard` are excluded from the
  scoped matrix.

## Changed Paths

- `ops/scripts/agent_workflow_gate_runner.py`
- `tests/test_agent_workflow_gate_runner.py`
- `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_MCP_SCOPE_2026-06-05.json`
- `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_MCP_SCOPE_2026-06-05.md`

## Verification

- `python -m pytest tests/test_agent_workflow_gate_runner.py -q`
  - Passed: `20`.
- `python -m py_compile ops/scripts/agent_workflow_gate_runner.py`
  - Passed.
- `python ops/scripts/agent_workflow_gate_runner.py --smoke-scope mcp --max-gates 1 --json-out docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_MCP_SCOPE_2026-06-05.json --markdown-out docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_MCP_SCOPE_2026-06-05.md`
  - Passed: `agent workflow gate matrix valid: workflows=2, scope=mcp, mode=dry_run, selected=2, passed=0, failed=0, skipped=0, reused=0`.

## Next Cycle

- Continue using the live source digest, but prefer targets that reduce launch
  operator ambiguity or strengthen checked evidence without requiring external
  credentials.

## Audit Marker

- `global_objective_complete=false`
