# AutoResearch: Agent Workflow Gate Matrix

## Objective

Move from single-workflow gate execution to a launch matrix that verifies every
declared active workflow through safe project-owned quality gates.

## Sources Checked

- `evalstate/fast-agent`: `https://github.com/evalstate/fast-agent`
- `langchain-ai/langgraph`: `https://github.com/langchain-ai/langgraph`
- `dsifry/metaswarm`: `https://github.com/dsifry/metaswarm`
- `crewAIInc/crewAI`: `https://github.com/crewAIInc/crewAI`

## A/B Contract

- Baseline: `agent_workflow_gate_runner.py` could run one workflow at a time,
  so launch evidence still required manual repetition across workflow IDs.
- Variant: add `--all-workflows` matrix mode that executes or plans the
  selected gates for every declared workflow, aggregates workflow/gate counts,
  and preserves the existing side-effect skip policy.
- Primary KPI: execute the first deterministic gate for all active workflows
  and produce durable evidence with `workflow_count=6`, `selected_gates=6`,
  `passed_gates=6`, and `failed_gates=0`.
- Guardrail: do not run side-effecting gates in matrix mode without
  `--allow-side-effect-gates`, keep dry-run available, and keep the completion
  audit global objective open.
- Decision rule: adopt only if matrix tests pass, script compilation passes,
  the real matrix run reports `status=pass`, and pre-push protects a cheap
  matrix dry-run.

## Adopted Variant

Adopted. The runner now provides a CrewAI-flow-style launch control surface:
it can verify every declared workflow through deterministic project-owned gates
without promoting a free-form agent runtime.

- Script: `ops/scripts/agent_workflow_gate_runner.py`
- Tests: `tests/test_agent_workflow_gate_runner.py`
- Generated JSON:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
- Generated Markdown:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`

## Runtime Evidence

Executed command:

```powershell
python ops\scripts\agent_workflow_gate_runner.py --all-workflows --execute --max-gates 1 --timeout 1200 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md
```

Result:

- execution mode `execute`
- workflows `6`
- selected gates `6`
- passed gates `6`
- failed gates `0`
- skipped gates `0`
- elapsed seconds `1161.195`
- covered workflow IDs: `dailynews-x-ops`, `getdaytrends-operator-run`,
  `desci-launch-readiness`, `agriguard-qr-product-verification`,
  `canva-widget-oauth-preview`, `workspace-quality-dashboard`

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q -p no:cacheprovider`
  - `15 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- matrix execution command above
  - `status=pass`
  - `workflow_count=6`
  - `passed_workflows=6`
  - `passed_gates=6`
- `python -m pytest tests\test_agent_workflow_gate_runner.py tests\test_agent_workflow_manifest.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `30 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_agent_workflow_gate_runner.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `72 passed`
- Hook script checks:
  - dev-server MCP runtime smoke: `5` requests, `5` tools
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - single-workflow dry-run: `workspace-quality-dashboard`, selected `1`
  - side-effect safety check: `desci-launch-readiness`, selected `1`,
    skipped `1`
  - matrix dry-run: workflows `6`, selected `6`
  - completion audit: `14` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`

## Remaining Boundary

This is a launch gate matrix, not a hosted autonomous runtime. Full stateful
orchestration, durable agent memory, human approval UI, live CrewAI/LangGraph
deployment, and credential-bound external tool execution remain future-scoped.
