# AutoResearch MCP Trace HTML Report - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: MCP eval evidence should include browser-readable HTML reports alongside JSON and Markdown outputs.

## A/B Contract

- Baseline: MCP trace metrics produced JSON plus Markdown reports, but the `lastmile-ai/mcp-eval` radar gap still included HTML report evidence.
- Variant: add a deterministic standalone HTML report writer for the same MCP smoke trace metrics.
- Primary KPI: make MCP smoke trace evidence reviewable as a checked-in HTML artifact without a separate frontend build.
- Guardrails: keep the smoke runner unchanged, preserve existing JSON/stdout/Markdown behavior, escape HTML content, and keep generated `var/` JSON unstaged.
- Decision: accepted. The variant closes the local HTML report gap while leaving full OpenTelemetry span trees, token/cost metrics, and cross-step causality future scoped.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Adds `--html-out`.
  - Emits a standalone HTML report with source metadata, summary counts, runtime-kind table, per-check metrics table, and trace-integrity status.
  - Escapes dynamic values before inserting them into HTML.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers HTML formatting, escaping, and CLI JSON+Markdown+HTML output.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Tracks the generated browser-readable metrics report.
- `ops/references/github_modernization_sources.json`
  - Records the HTML report as local evidence for the `lastmile-ai/mcp-eval` source row.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `6/6`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-html-report-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.md --html-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Passed.
  - HTML report summary: `checks=6`, `passed=6`, `failed=0`, `observed_checks=4`, `missing_checks=2`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-html-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- This does not claim full `mcp-eval` parity. Remaining source-backed work is full OpenTelemetry span trees, token/cost metrics, and cross-step causality.
