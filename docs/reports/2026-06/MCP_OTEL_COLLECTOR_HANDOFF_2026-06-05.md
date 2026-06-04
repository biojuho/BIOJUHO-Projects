# MCP OTLP Collector Handoff

- Status: `pass`
- Source: `open-telemetry/opentelemetry-collector`
- Source URL: https://github.com/open-telemetry/opentelemetry-collector
- Source docs: https://opentelemetry.io/docs/collector/
- Collector runtime: `future_scoped_operator_owned`
- Default behavior: `offline_local_file`
- OTLP JSONL: `var\workspace-smoke-mcp-otel-handoff-2026-06-05.otlp.jsonl`
- Lines: `1`
- Resource spans: `1`
- Scope spans: `1`
- Spans: `3`

## Required Resource Attributes

- `service.name`: `1`
- `service.namespace`: `1`
- `workspace_smoke.exporter`: `1`
- `workspace_smoke.signal`: `1`

## Required Span Attributes

- `workspace_smoke.scope`: `3`
- `workspace_smoke.check.name`: `3`
- `workspace_smoke.cwd`: `3`
- `workspace_smoke.command`: `3`
- `workspace_smoke.command.kind`: `3`
- `workspace_smoke.returncode`: `3`
- `workspace_smoke.ok`: `3`
- `workspace_smoke.elapsed_seconds`: `3`

## Operator Decisions Required

- collector distribution and deployment target
- OTLP endpoint and credentials
- retention policy
- sampling and processor policy
- failure and retry handling

## Errors

- none
