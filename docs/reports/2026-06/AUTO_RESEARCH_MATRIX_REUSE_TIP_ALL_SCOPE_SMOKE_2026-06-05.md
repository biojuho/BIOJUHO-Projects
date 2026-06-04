# AutoResearch: Matrix Reuse Tip All-Scope Smoke

## Objective

Refresh the launch all-scope proof after the workflow matrix reuse optimization
landed on the active branch.

## Current Tip

- Branch: `feat/observability-gateway-2026-05`
- Commit: `77cc93d`
- Latest slice: `feat(ops): reuse duplicate workflow gates`
- Generated at: `2026-06-05T02:12:39+09:00`

## A/B Contract

- Baseline: the previous active all-scope proof covered `39d6a82`, before the
  matrix reuse optimization changed `agent_workflow_gate_runner.py`.
- Variant: rerun the canonical all-scope smoke on the matrix-reuse tip with
  MCP trace and OTLP span exports enabled.
- Primary KPI: `run_workspace_smoke.py --scope all` returns `total=25`,
  `passed=25`, and `failed=0`.
- Guardrails: keep MCP trace and OTLP evidence, update the completion contract
  proof commit to `77cc93d`, and keep the global objective open.
- Decision rule: adopt this proof only if the all-scope smoke passes on the
  current remote tip and no newer remote commit appears before recording.

## All-Scope Evidence

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.json --mcp-trace-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.otlp.jsonl
```

Result:

- `total=25`
- `passed=25`
- `failed=0`
- Duration: `598.448s`
- MCP trace events: `3`
- OTLP lines: `1`
- OTLP spans: `3`

## Scope Summary

- `workspace`: `6/6 PASS` in `84.17s`
- `desci`: `7/7 PASS` in `228.598s`
- `agriguard`: `5/5 PASS` in `108.227s`
- `mcp`: `3/3 PASS` in `65.772s`
- `getdaytrends`: `2/2 PASS` in `81.365s`
- `cie`: `2/2 PASS` in `29.855s`

## Repo-Owned Evidence

- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.json`
- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.trace.jsonl`
- `docs/reports/2026-06/WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.otlp.jsonl`

## Decision

Adopted as the active launch all-scope proof for the matrix-reuse branch tip.
The global objective remains intentionally open because the AutoResearch loop is
still user-stopped and credential/runtime boundaries remain future-scoped.
