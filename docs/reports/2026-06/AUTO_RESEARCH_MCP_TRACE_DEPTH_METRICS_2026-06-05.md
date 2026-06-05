# AutoResearch MCP Trace Depth Metrics - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URLs:
  - https://github.com/lastmile-ai/mcp-eval
  - https://mcp-eval.ai/metrics-tracing
- Pattern adopted: MCP evaluation artifacts should expose trace-derived timing and path-shape metrics, not only pass/fail counts.

## A/B Contract

- Baseline: `ops/scripts/mcp_smoke_trace_metrics.py` validated trace integrity and summarized checks, runtime kinds, cwd coverage, and pass/fail counts.
- Variant: derive low-risk offline timing and path-depth signals from existing schema v1 workspace-smoke JSON without changing smoke execution.
- Primary KPI: make MCP smoke artifacts easier to audit for slow checks and path complexity during handoff reviews.
- Guardrails: keep the smoke runner contract unchanged, preserve existing CLI behavior, and tolerate compile checks that do not expose duration text.
- Decision: accepted. The variant closes the local timing/path-depth gap while leaving full OTEL span-tree integration future scoped.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Parses explicit duration fields when future reports provide them.
  - Derives durations from common pytest and build output tails such as `passed in 117.48s` and `built in 820ms`.
  - Emits per-check `duration_seconds`, `duration_source`, `cwd_depth`, `command_path_tokens`, and `command_path_depth`.
  - Adds summary-level timing and path-depth sections.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers stdout-derived durations, millisecond conversion, explicit duration fields, cwd depth, command path depth, and CLI JSON output.
- `ops/references/github_modernization_sources.json`
  - Updates the `lastmile-ai/mcp-eval` row with the new evidence and narrows the remaining gap.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q`
  - Passed `4/4`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-depth-metrics-2026-06-05.json`
  - Passed.
  - Metrics summary: `checks=6`, `passed=6`, `failed=0`.
  - Timing: `observed_checks=4`, `missing_checks=2`, `total_seconds=119.43`, `max_seconds=117.48`, `slowest_check=DailyNews unit tests`.
  - Path depth: `max_cwd_depth=2`, `max_command_path_depth=5`, `command_path_tokens=14`.
  - Trace integrity: `ok=true`, no issues.

## Notes

- The generated metrics JSON stays under `var/` and is not staged.
- This does not claim full `mcp-eval` parity. Remaining source-backed work is full OpenTelemetry span trees, token/cost metrics, and cross-step causality.
