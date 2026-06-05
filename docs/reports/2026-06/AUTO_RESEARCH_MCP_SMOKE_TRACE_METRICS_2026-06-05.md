# AutoResearch MCP Smoke Trace Metrics - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: real MCP execution should produce operator-readable trace and metric evidence, not only pass/fail text.

## A/B Contract

- Baseline: `run_workspace_smoke.py --scope mcp` already writes schema v1 JSON with per-check command traces, but operators had to inspect raw results manually to understand MCP runtime coverage.
- Variant: add a small post-processor that validates MCP smoke trace integrity and summarizes runtime kinds, working directories, checks, and pass/fail counts.
- Primary KPI: make MCP smoke artifacts easier to audit in CI and handoff reviews.
- Guardrails: do not modify the already-dirty smoke runner; consume existing schema v1 JSON only.
- Decision: accepted. The variant adds trace metrics without changing smoke execution behavior.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Reads schema v1 workspace-smoke JSON.
  - Filters the requested scope, defaulting to `mcp`.
  - Emits check counts, pass/fail counts, command runtime kinds, cwd coverage, and trace-integrity issues.
  - Returns nonzero when trace integrity fails unless `--allow-issues` is used.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers runtime-kind summaries, integrity issue detection, and CLI JSON output.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q`
  - Passed `3/3`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-metrics-canva-tool-inventory-2026-06-05.json`
  - Passed.
  - Metrics summary: `checks=6`, `passed=6`, `failed=0`.
  - Runtime kinds: `compileall=2`, `pytest=3`, `npm=1`.
  - Trace integrity: `ok=true`, no issues.

## Notes

- This does not replace full MCP eval tooling or OpenTelemetry. It creates a low-risk local bridge from existing smoke artifacts to auditable MCP trace metrics.
- The generated metrics JSON lives under `var/` and is not staged; this report records the operator evidence.
