# AutoResearch: Agent Workflow Gate Safety

## Objective

Prevent the bounded agent workflow runner from accidentally starting
long-running or side-effecting local services during `--execute` runs unless an
operator explicitly allows those gates.

## Sources Checked

- `evalstate/fast-agent`: `https://github.com/evalstate/fast-agent`
- `langchain-ai/langgraph`: `https://github.com/langchain-ai/langgraph`
- Existing local workflow gate runner:
  `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`

## A/B Contract

- Baseline: `agent_workflow_gate_runner.py` could execute selected manifest
  gates, but side-effecting commands such as dev-server starts were only
  avoided by manually choosing `--max-gates 1`.
- Variant: classify gate safety, add `--gate-index` for targeted gate checks,
  skip side-effecting gates by default in execute mode, and require
  `--allow-side-effect-gates` as the explicit operator override.
- Primary KPI: execute a targeted side-effecting DeSci gate in the real
  manifest and produce durable evidence with `skipped_gates=1` and no
  subprocess launch.
- Guardrail: deterministic smoke/test gates must still run, skipped gates must
  remain visible in JSON/Markdown, and the completion audit must keep the
  global objective open.
- Decision rule: adopt only if unit tests pass, script compilation passes, the
  real targeted gate safety proof reports `status=pass`, and pre-push protects
  the safety path.

## Adopted Variant

Adopted. The runner now implements a LangGraph-style human-checkpoint boundary:
side-effecting gates are visible and selectable, but execute-mode runs skip them
unless the operator supplies `--allow-side-effect-gates`.

- Script: `ops/scripts/agent_workflow_gate_runner.py`
- Tests: `tests/test_agent_workflow_gate_runner.py`
- Generated JSON:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
- Generated Markdown:
  `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.md`

## Runtime Evidence

Executed command:

```powershell
python ops\scripts\agent_workflow_gate_runner.py --workflow desci-launch-readiness --execute --gate-index 2 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.md
```

Result:

- workflow `desci-launch-readiness`
- execution mode `execute`
- requested gate index `2`
- selected gates `1`
- passed gates `0`
- failed gates `0`
- skipped gates `1`
- safety risk `side_effecting`
- skip reason includes `--allow-side-effect-gates`

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q -p no:cacheprovider`
  - `11 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- targeted safety proof command above
  - `status=pass`
  - `selected=1`
  - `skipped=1`
  - no dev-server subprocess was launched
- `python -m pytest tests\test_agent_workflow_gate_runner.py tests\test_agent_workflow_manifest.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `26 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_agent_workflow_gate_runner.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `68 passed`
- Hook script checks:
  - dev-server MCP runtime smoke: `5` requests, `5` tools
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - runner dry-run: `workspace-quality-dashboard`, selected `1`, skipped `0`
  - side-effect safety check: `desci-launch-readiness`, selected `1`,
    skipped `1`
  - completion audit: `13` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`

## Remaining Boundary

The override is intentionally explicit. Full stateful workflow orchestration,
durable agent memory, hosted execution, and human approval UI remain
future-scoped until the operator owns those runtime policies.
