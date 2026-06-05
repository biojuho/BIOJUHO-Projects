# AutoResearch MCP Trace OTEL Submit - 2026-06-05

## Source Signal

- Upstream: `lastmile-ai/mcp-eval`
- URL: https://github.com/lastmile-ai/mcp-eval
- Supporting protocol source: https://opentelemetry.io/docs/specs/otlp/
- Pattern adopted: trace-derived MCP evidence should have an opt-in OTLP/HTTP JSON submission path, not only offline export files.

## A/B Contract

- Baseline: MCP trace metrics could generate deterministic OTEL-style JSON but could not submit it to a collector endpoint.
- Variant: add an explicit `--otel-submit-url` path that POSTs the generated JSON to an OTLP/HTTP traces endpoint and records the submission result.
- Primary KPI: prove the generated trace export can cross the process boundary into a collector-compatible HTTP receiver.
- Guardrails: no implicit network submission, no header-value persistence, no live SDK instrumentation claim, and no collector dependency for normal metrics/report generation.
- Decision: accepted. Collector submission is now covered by code, tests, and a local `/v1/traces` evidence run.

## Changes

- `ops/scripts/mcp_smoke_trace_metrics.py`
  - Adds `--otel-submit-url`, `--otel-submit-timeout-seconds`, `--otel-submit-header`, `--otel-submit-report-out`, and `--allow-otel-submit-failure`.
  - POSTs OTEL JSON with `Content-Type: application/json`.
  - Writes submission evidence with endpoint, status code, request bytes, response preview, and header names only.
- `tests/test_mcp_smoke_trace_metrics.py`
  - Covers direct submission to a local collector endpoint.
  - Covers CLI submission plus persisted submission report.
- `docs/reports/2026-06/MCP_SMOKE_TRACE_OTEL_SUBMIT_2026-06-05.json`
  - Tracks a local collector run at `http://127.0.0.1:4318/v1/traces`.

## Verification

- `python -m py_compile ops\scripts\mcp_smoke_trace_metrics.py`
  - Passed.
- `python -m pytest tests\test_mcp_smoke_trace_metrics.py -q --tb=line -p no:cacheprovider`
  - Passed `10/10`.
- Local collector submission run:
  - Endpoint: `http://127.0.0.1:4318/v1/traces`
  - Status: `202`
  - Request bytes: `4362`
  - Local capture path: `/v1/traces`
  - Local capture content type: `application/json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-trace-otel-submit-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Remaining Scope

- This is still an offline trace derivation and opt-in HTTP submit path.
- Live token/cost emission from upstream agent or model runs remains future scoped work.
