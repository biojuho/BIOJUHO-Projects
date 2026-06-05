# AutoResearch MCP Trace Live Usage Emission - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Pattern adopted: real command execution should be able to emit token and cost usage into trace evidence, not only rely on offline or hand-authored metrics.

## A/B Contract

- Baseline: MCP trace metrics could summarize usage fields if present, but the workspace smoke runner had no live subprocess channel for emitting them.
- Variant: add a per-check `WORKSPACE_SMOKE_USAGE_OUT` sidecar path. A running command can write usage JSON, and the smoke runner normalizes safe token/cost fields into the schema-v1 result.
- Primary KPI: produce a real smoke JSON artifact whose result contains observed token and cost usage from a subprocess emission path.
- Guardrails: do not require model providers, do not fabricate default usage for commands that emit none, and preserve existing JSON reports by omitting empty usage fields.
- Decision: accepted. Live usage emission is now covered by code, tests, raw smoke evidence, trace metrics, and OTEL-style trace export.

## Changes

- `ops/scripts/run_workspace_smoke.py`
  - Exposes `WORKSPACE_SMOKE_USAGE_OUT` to each check process.
  - Reads `usage.json` from the check temp directory after execution.
  - Accepts canonical and provider-style aliases: `input_tokens`/`prompt_tokens`, `output_tokens`/`completion_tokens`, `total_tokens`/`tokens`, and `cost_usd`/`estimated_cost_usd`.
  - Omits empty usage fields from schema-v1 JSON results.
- `tests/test_workspace_smoke_usage_sidecar.py`
  - Covers a real child process writing usage to the sidecar.
  - Covers JSON report compatibility for results with and without usage fields.
- `automation/DailyNews/src/antigravity_mcp/integrations/llm/client_wrapper.py`
  - Emits the same sidecar from completed LLM wrapper calls when token metadata is present.
- `tests/test_dailynews_llm_usage_sidecar.py`
  - Covers the LLM wrapper sidecar payload from generation metadata.
- `docs/reports/2026-06/WORKSPACE_SMOKE_USAGE_SIDECAR_2026-06-05.json`
  - Tracks the raw smoke report from the live sidecar probe.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.json`
  - Tracks the trace metrics summary over the sidecar smoke report.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_USAGE_SIDECAR_OTEL_2026-06-05.json`
  - Tracks the OTEL-style trace export over the sidecar smoke report.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py`
  - Passed.
- `python -m py_compile ops\scripts\run_workspace_smoke.py automation\DailyNews\src\antigravity_mcp\integrations\llm\client_wrapper.py`
  - Passed.
- `python -m pytest tests\test_workspace_smoke_usage_sidecar.py tests\test_dailynews_llm_usage_sidecar.py tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `13/13`.
- Live sidecar probe:
  - Raw smoke report: `docs/reports/2026-06/WORKSPACE_SMOKE_USAGE_SIDECAR_2026-06-05.json`
  - Result fields: `input_tokens=120`, `output_tokens=35`, `total_tokens=155`, `cost_usd=0.0042`.
- `python ops\scripts\mcp_smoke_trace_metrics.py docs\reports\2026-06\WORKSPACE_SMOKE_USAGE_SIDECAR_2026-06-05.json --json-out docs\reports\2026-06\MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.md --otel-json-out docs\reports\2026-06\MCP_SMOKE_TRACE_USAGE_SIDECAR_OTEL_2026-06-05.json`
  - Passed.
  - Usage summary: `1 observed`, `0 missing`, `155` total tokens, `$0.0042`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-live-usage-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=6`, `partially_adopted=0`, `watch=0`.

## Remaining Scope

- Commands that do not emit usage remain explicitly missing usage, which is intentional.
- Additional provider wrappers that bypass the DailyNews LLM wrapper can adopt `WORKSPACE_SMOKE_USAGE_OUT` when run under the smoke gate.
