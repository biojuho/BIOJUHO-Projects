# AutoResearch MCP Trace Markdown Report - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: MCP eval evidence should include CI-friendly human reports alongside machine JSON.

## A/B Contract

- Baseline: `ops/scripts/mcp_smoke_trace_metrics.py` emitted deterministic JSON metrics, but durable handoff evidence still required reading raw JSON or a chat summary.
- Variant: add a deterministic Markdown report writer for the same MCP trace metrics.
- Primary KPI: make the MCP smoke trace summary directly reviewable in repo reports and CI summaries.
- Guardrails: keep the smoke runner unchanged, preserve existing JSON/stdout behavior, and keep generated `var/` JSON unstaged.
- Decision: accepted. The variant adds tracked operator evidence without changing MCP smoke execution.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Adds `--markdown-out`.
  - Formats source metadata, summary counts, runtime-kind counts, per-check timing/path-depth rows, and trace-integrity status.
  - Escapes Markdown table cells deterministically.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers Markdown formatting, escaping, and CLI JSON+Markdown output.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - Tracks the generated operator report for the latest MCP smoke trace artifact.
- `ops/references/github_modernization_sources.json`
  - Records the Markdown report as local evidence for the `lastmile-ai/mcp-eval` source row.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `5/5`.
- `python ops\scripts\mcp_smoke_trace_metrics.py var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json --json-out var\mcp-smoke-trace-markdown-report-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - Passed.
  - Report summary: `checks=6`, `passed=6`, `failed=0`, `observed_checks=4`, `missing_checks=2`.
  - Slowest check: `DailyNews unit tests` at `117.48s`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-markdown-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=4`, `partially_adopted=2`, `watch=0`.

## Notes

- This does not claim full `mcp-eval` parity. Remaining source-backed work is full OpenTelemetry span trees, token/cost metrics, HTML reports, and cross-step causality.
