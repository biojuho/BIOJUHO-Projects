# AutoResearch: Agent Workflow Gate Matrix Reuse

## Objective

Optimize the all-workflows launch matrix by reusing identical deterministic
gate results instead of rerunning the same command for multiple workflows.

## Sources Checked

- `dsifry/metaswarm`: `https://github.com/dsifry/metaswarm`
- `crewAIInc/crewAI`: `https://github.com/crewAIInc/crewAI`
- Existing matrix evidence:
  `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`

## A/B Contract

- Baseline: the first real matrix run selected `6` gates, executed all `6`,
  passed all `6`, and took `1161.195s`.
- Variant: cache identical deterministic gate command results within a matrix
  run and mark duplicate gates as `reused` with a `reused_from` pointer.
- Primary KPI: reduce matrix elapsed time while preserving `workflow_count=6`,
  `selected_gates=6`, `failed_gates=0`, and visible per-workflow evidence.
- Guardrail: never reuse side-effecting gates, never hide reused gates from
  JSON/Markdown, and keep failed cached results failing if reused.
- Decision rule: adopt only if tests pass, script compilation passes, the real
  optimized matrix reports `status=pass`, and pre-push protects matrix dry-run.

## Adopted Variant

Adopted. The optimized matrix reused the duplicate MCP smoke gate for
`canva-widget-oauth-preview` from the earlier `dailynews-x-ops` MCP gate,
keeping six workflow checks visible while running five unique deterministic
commands.

- Script: `ops/scripts/agent_workflow_gate_runner.py`
- Tests: `tests/test_agent_workflow_gate_runner.py`
- Baseline JSON:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
- Optimized JSON:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
- Optimized Markdown:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`

## Runtime Evidence

Executed command:

```powershell
python ops\scripts\agent_workflow_gate_runner.py --all-workflows --execute --max-gates 1 --timeout 1200 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md
```

Result:

- execution mode `execute`
- workflows `6`
- selected gates `6`
- passed gates `5`
- reused gates `1`
- failed gates `0`
- skipped gates `0`
- elapsed seconds `834.845`
- baseline elapsed seconds `1161.195`
- improvement `326.350s` faster, about `28.1%`

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q -p no:cacheprovider`
  - `15 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- optimized matrix execution command above
  - `status=pass`
  - `workflow_count=6`
  - `selected_gates=6`
  - `reused_gates=1`
  - `failed_gates=0`
- `python -m pytest tests\test_agent_workflow_gate_runner.py tests\test_agent_workflow_manifest.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `32 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_agent_workflow_gate_runner.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `74 passed`
- Hook script checks:
  - dev-server MCP runtime smoke: `5` requests, `5` tools
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - single-workflow dry-run: `workspace-quality-dashboard`, selected `1`
  - side-effect safety check: `desci-launch-readiness`, selected `1`,
    skipped `1`
  - matrix dry-run: workflows `6`, selected `6`
  - completion audit: `16` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`

## Remaining Boundary

This optimizes deterministic matrix execution only. Side-effecting gates remain
explicitly skipped unless `--allow-side-effect-gates` is supplied, and hosted
agent orchestration remains future-scoped.
