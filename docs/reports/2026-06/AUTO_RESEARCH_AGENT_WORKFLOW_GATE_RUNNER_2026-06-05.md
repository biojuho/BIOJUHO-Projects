# AutoResearch: Agent Workflow Gate Runner

## Objective

Close the next concrete slice of the live agent workflow orchestration gap by
executing declared workflow quality gates through existing project CLIs. This is
a bounded gate runner, not a free-form autonomous agent runtime.

## Sources Checked

- `evalstate/fast-agent`: `https://github.com/evalstate/fast-agent`
- `langchain-ai/langgraph`: `https://github.com/langchain-ai/langgraph`
- Existing local workflow manifest:
  `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`

## A/B Contract

- Baseline: `agent_workflow_manifest.py` could validate workflows and render
  dry-run plans, but it could not execute a declared quality gate and persist a
  machine-readable result.
- Variant: add `ops/scripts/agent_workflow_gate_runner.py` to run selected
  workflow quality gates through the existing CLI/smoke commands, with dry-run
  as the default and explicit `--execute` for bounded execution.
- Primary KPI: execute one declared `workspace-quality-dashboard` quality gate
  and pass it with durable JSON and Markdown evidence.
- Guardrail: do not introduce a free-form agent runtime, do not execute
  side-effecting browser/server actions unless selected by an explicit gate, and
  keep full LangGraph-style stateful orchestration future-scoped.
- Decision rule: adopt only if unit tests pass, script compilation passes, the
  real gate run reports `status=pass`, and the completion audit keeps the
  global objective open.

## Adopted Variant

Adopted. The workspace can now move from workflow dry-run plans to bounded
quality-gate execution without bypassing existing project-owned checks.

- Script: `ops/scripts/agent_workflow_gate_runner.py`
- Tests: `tests/test_agent_workflow_gate_runner.py`
- Generated JSON:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json`
- Generated Markdown:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md`

## Runtime Evidence

Executed command:

```powershell
python ops\scripts\agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --execute --max-gates 1 --timeout 900 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md
```

Result:

- workflow `workspace-quality-dashboard`
- execution mode `execute`
- selected gates `1`
- passed gates `1`
- failed gates `0`
- elapsed seconds `191.444`
- gate command:
  `python ops/scripts/run_workspace_smoke.py --scope workspace`
- nested workspace smoke result: `6/6 PASS`

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q -p no:cacheprovider`
  - `5 passed`
- `python -m pytest tests\test_agent_workflow_gate_runner.py tests\test_agent_workflow_manifest.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `20 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- `python ops\scripts\agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --execute --max-gates 1 --timeout 900 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md`
  - `status=pass`
  - `selected_gates=1`
  - `passed_gates=1`
  - nested workspace smoke `6/6 PASS`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_agent_workflow_gate_runner.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `62 passed`
- Hook script checks:
  - dev-server MCP runtime smoke: `5` requests, `5` tools, `mutation_guard=process_mutation_disabled`
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - agent workflow gate runner dry-run: `mode=dry_run`, `selected=1`
  - completion audit: `12` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`

## Remaining Boundary

Full stateful autonomous workflow orchestration, durable agent memory, human
approval checkpoints, and hosted deployment remain future-scoped. The adopted
variant intentionally stays behind the existing project CLIs and smoke gates.
