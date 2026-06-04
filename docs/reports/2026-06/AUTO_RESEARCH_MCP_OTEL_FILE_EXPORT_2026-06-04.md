# AutoResearch: MCP OTLP File Export

Date: 2026-06-04

## Source-backed prompt

- GitHub source: `lastmile-ai/mcp-eval`
- Standards sources:
  - OpenTelemetry Protocol File Exporter: `https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/`
  - OpenTelemetry Trace API: `https://opentelemetry.io/docs/specs/otel/trace/api/`
- Local gap: MCP smoke already had schema-level trace metrics and JSONL events, but no span-shaped local contract for tools that ingest OpenTelemetry Protocol file-exporter output.
- Constraint: keep the default smoke gate deterministic and offline. Do not require a live collector or OpenTelemetry SDK dependency.

## A/B contract

- Baseline: `--mcp-trace-out` writes one lightweight `workspace_smoke.mcp_check`
  event per completed MCP check.
- Variant: add an opt-in `--mcp-otel-out` writer that emits one OTLP
  file-exporter-style JSONL object with `resourceSpans`, `scopeSpans`, and one
  span per completed MCP check.
- KPI: a real MCP smoke run writes `3` span records with stable trace/span IDs,
  nanosecond start/end fields, status codes, and `workspace_smoke.*`
  attributes while still passing `3/3`.

## Adopted variant

The OTLP file-export variant was adopted.

Implementation:

- `ops/scripts/run_workspace_smoke.py` now records `started_at_unix_nano` and
  `ended_at_unix_nano` on each result.
- `--mcp-otel-out <path>` writes a local OTLP-shaped JSONL file and refreshes it
  after each completed check, matching the existing partial-evidence behavior.
- `tests/test_workspace_smoke.py` covers the OTLP shape, writer replacement, and
  CLI wiring.
- `docs/QUALITY_GATE.md` documents the new flag, result timing fields, and span
  attributes.
- The GitHub modernization radar now records local OTLP file-exporter shaped
  span export as adopted while keeping live collector shipping future-scoped.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py` -> PASS
- `python -m pytest tests\test_workspace_smoke.py -q -p no:cacheprovider`
  -> `27 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py tests\test_github_modernization_radar.py tests\test_mcp_service_manifest.py tests\test_dev_server_status.py tests\test_agent_workflow_manifest.py -q -p no:cacheprovider`
  -> `56 passed` after rebasing on remote tip `ace5ca4`
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.json --mcp-trace-out var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.otlp.jsonl`
  -> `3/3 PASS`

Live artifact summary:

- `var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.json`:
  `total=3`,
  `completed=3`, `passed=3`, `failed=0`
- `mcp_trace.command_kinds`: `compileall=2`, `pytest=1`
- `duration_seconds`: `72.274`
- `var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.trace.jsonl`:
  `3` `workspace_smoke.mcp_check` events
- `var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.otlp.jsonl`:
  `1` `resourceSpans` line with `3` spans
- Span names:
  `workspace_smoke.mcp_check notebooklm compile`,
  `workspace_smoke.mcp_check github-mcp compile`,
  `workspace_smoke.mcp_check DailyNews unit tests`
- Span statuses: `1`, `1`, `1`
- Span elapsed seconds: `0.301`, `0.299`, `71.637`

## Remaining gap

Live OpenTelemetry SDK or collector shipping is still future-scoped. The launch
gate now has a deterministic local file contract that can be consumed by a
scheduled collector later without making the default smoke run network-bound.
