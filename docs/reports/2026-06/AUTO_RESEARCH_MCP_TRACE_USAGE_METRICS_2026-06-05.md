# AutoResearch MCP Trace Usage Metrics - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: MCP eval evidence should surface token and cost usage where trace artifacts provide usage fields.

## A/B Contract

- Baseline: MCP trace metrics summarized timing, path depth, runtime kinds, and reports, but did not preserve token or cost usage fields from smoke artifacts.
- Variant: add optional token/cost extraction and summaries without changing smoke execution or inventing usage values.
- Primary KPI: make future MCP smoke artifacts usage-aware while honestly reporting current usage coverage.
- Guardrails: do not synthesize token/cost data, tolerate reports with no usage fields, and keep existing JSON/Markdown/HTML outputs deterministic.
- Decision: accepted as support infrastructure. Current MCP smoke evidence has no usage fields, so the generated report records `0 observed, 6 missing`.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Extracts flat or nested usage fields such as `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, and `usage.prompt_tokens`.
  - Derives `total_tokens` only when input and output token counts are both present.
  - Adds summary-level usage counts, token totals, cost totals, max token check, and costliest check.
  - Adds per-check token/cost columns to Markdown and HTML reports.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers flat usage fields, nested usage fields, derived totals, cost rounding, no-usage coverage, and report columns.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - Regenerated with usage coverage shown as `0 observed, 6 missing`.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Regenerated with usage coverage and token/cost columns.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `7/7`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-usage-report-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.md --html-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - Passed.
  - Current usage coverage: `observed_checks=0`, `missing_checks=6`, `total_tokens=null`, `cost_usd=null`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-usage-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- This does not claim live token or cost emission. It makes the trace metrics pipeline ready to preserve and report those values when the smoke runner or upstream tools produce them.
