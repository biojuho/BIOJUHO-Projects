# AutoResearch: Workflow Matrix Tip All-Scope Smoke

## Objective

Refresh the launch all-scope proof on the actual remote branch tip after the
agent workflow gate matrix landed. This is the active product launch gate proof
for branch `feat/observability-gateway-2026-05`.

## Current Tip

- Branch: `feat/observability-gateway-2026-05`
- Commit: `39d6a82`
- Latest slice: `feat(ops): add workflow gate matrix`
- Generated at: `2026-06-05T01:45:50+09:00`

## A/B Contract

- Baseline: the previous launch proof predated the all-workflows matrix mode
  and the expanded hook guard.
- Variant: rerun the canonical all-scope smoke on the workflow-matrix tip with
  MCP trace and OTLP span exports enabled.
- Primary KPI: `run_workspace_smoke.py --scope all` returns `total=25`,
  `passed=25`, and `failed=0`.
- Guardrails: the current hook-equivalent fast gate passes, the workflow
  matrix dry-run remains valid, side-effecting gates stay skipped by default,
  and the completion audit keeps the open-ended global objective incomplete
  until the user explicitly stops.
- Decision rule: adopt this proof only if the fast gate and all-scope smoke
  both pass on `39d6a82`.

## Fast Gate Evidence

- `python -m pytest tests/test_workspace_smoke.py tests/test_autoresearch_completion_audit.py tests/test_mcp_service_runtime_smoke.py tests/test_mcp_otel_collector_handoff.py tests/test_agent_workflow_gate_runner.py tests/test_dev_server_browser_smoke.py tests/test_dev_server_mcp_contract.py tests/test_dev_server_mcp_runtime.py tests/test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `72 passed`
- `python ops/scripts/dev_server_mcp_runtime_smoke.py`
  - `5` requests, `5` tools, `mutation_guard=process_mutation_disabled`
- `python ops/scripts/mcp_service_runtime_smoke.py`
  - `3` services checked, `3` passed, `39` tools
- `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
  - dry-run valid, selected `1` gate
- `python ops/scripts/agent_workflow_gate_runner.py --workflow desci-launch-readiness --execute --gate-index 2`
  - execute mode valid, selected `1` gate, skipped `1` side-effecting gate
- `python ops/scripts/agent_workflow_gate_runner.py --all-workflows --max-gates 1`
  - matrix dry-run valid, workflows `6`, selected gates `6`
- `python ops/scripts/autoresearch_completion_audit.py --json-out var/autoresearch-completion-audit-workflow-matrix-tip-fast-2026-06-05.json`
  - `14` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`

## All-Scope Evidence

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.json --mcp-trace-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.otlp.jsonl
```

Result:

- `total=25`
- `passed=25`
- `failed=0`
- Duration: `601.252s`
- MCP trace events: `3`
- OTLP lines: `1`
- OTLP spans: `3`

## Scope Summary

- `workspace`: `6/6 PASS` in `82.753s`
- `desci`: `7/7 PASS` in `230.402s`
- `agriguard`: `5/5 PASS` in `102.991s`
- `mcp`: `3/3 PASS` in `79.596s`
- `getdaytrends`: `2/2 PASS` in `81.578s`
- `cie`: `2/2 PASS` in `23.42s`

## Repo-Owned Evidence

- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.json`
- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.trace.jsonl`
- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.otlp.jsonl`
- `var/autoresearch-completion-audit-workflow-matrix-tip-fast-2026-06-05.json`

## Decision

Adopted as the active launch all-scope proof for the current branch tip. The
global objective remains intentionally open because the user requested a
continuous AutoResearch loop until explicit stop, while external-auth and
operator-owned runtime boundaries remain future-scoped.
