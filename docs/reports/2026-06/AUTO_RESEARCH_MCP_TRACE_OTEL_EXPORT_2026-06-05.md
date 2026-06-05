# AutoResearch MCP Trace OTEL Export - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: trace-derived MCP evidence should be exportable in an OpenTelemetry-style span shape, not only as custom JSON tables.

## A/B Contract

- Baseline: MCP trace metrics included an offline span tree in custom JSON, Markdown, and HTML, but no OTEL-style export artifact.
- Variant: add a deterministic `--otel-json-out` writer that converts the derived root/check spans into a `resourceSpans` JSON structure.
- Primary KPI: make the offline MCP trace structure easier to bridge into collectors or OTEL tooling.
- Guardrails: do not submit to a collector, do not fabricate timestamps, and do not claim live OTEL instrumentation.
- Decision: accepted as an offline OTEL-style export. Live token/cost emission and collector submission remain future scoped.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Adds `--otel-json-out`.
  - Emits `resourceSpans` with deterministic `traceId`, `spanId`, `parentSpanId`, status codes, and MCP attributes.
  - Preserves previous-step links as `mcp.previous_span_id` attributes.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers deterministic OTEL-style span export, parent IDs, status mapping, and CLI output.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_OTEL_2026-06-05.json`
  - Tracks the generated OTEL-style export for the current MCP smoke artifact.
- `ops/references/github_modernization_sources.json`
  - Records the OTEL-style export as `lastmile-ai/mcp-eval` evidence.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `8/8`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-otel-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.md --html-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.html --otel-json-out docs\reports\2026-06\MCP_SMOKE_TRACE_OTEL_2026-06-05.json`
  - Passed.
  - Export summary: one root span plus six child spans.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-otel-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- This is an offline OTEL-style artifact, not live OpenTelemetry SDK instrumentation and not collector submission.
