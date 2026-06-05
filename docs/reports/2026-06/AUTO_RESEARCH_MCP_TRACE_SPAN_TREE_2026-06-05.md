# AutoResearch MCP Trace Span Tree - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: trace evidence should show parent/child span shape and cross-step ordering, not only flat check rows.

## A/B Contract

- Baseline: MCP trace metrics exposed per-check timing, path, usage, and reports, but the checks were still flat rows.
- Variant: add an offline span tree with one root span, one child span per MCP check, and `previous_span_id` links that preserve deterministic smoke execution order.
- Primary KPI: make cross-step order and parent-child relationships auditable in JSON, Markdown, and HTML artifacts.
- Guardrails: do not claim OpenTelemetry export, do not change smoke execution, and keep the derived span IDs deterministic.
- Decision: accepted as offline trace-structure evidence. Full OTEL export remains future scoped work.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Adds top-level `span_tree` with root span metadata, summary counts, and ordered check spans.
  - Adds `previous_span_id` links so reviewers can inspect cross-step order.
  - Adds a Span Tree section to Markdown and HTML reports.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers root span, child span count, linked span count, previous-step links, Markdown output, and HTML output.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - Regenerated with the Span Tree table.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Regenerated with the Span Tree table.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `7/7`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-span-tree-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.md --html-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Passed.
  - Generated `6` child spans under `mcp:root`; linked spans: `5`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-span-tree-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- This is an offline span tree derived from deterministic smoke output. It is intentionally not full OpenTelemetry export.
