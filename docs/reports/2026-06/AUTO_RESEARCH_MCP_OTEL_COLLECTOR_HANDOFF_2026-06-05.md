# AutoResearch: MCP OTLP Collector Handoff

## Objective

Close the observability handoff gap left after the local MCP OTLP file-export
slice. The goal is not to ship a live collector without operator decisions; the
goal is to prove that a real `--mcp-otel-out` artifact is ready for an
operator-owned OpenTelemetry Collector or scheduled shipper.

## Sources Checked

- OpenTelemetry Collector GitHub repository:
  `https://github.com/open-telemetry/opentelemetry-collector`
- OpenTelemetry Collector documentation:
  `https://opentelemetry.io/docs/collector/`
- Existing local OTLP file-export report:
  `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_FILE_EXPORT_2026-06-04.md`

## A/B Contract

- Baseline: `run_workspace_smoke.py --mcp-otel-out` emitted a local
  OTLP-shaped JSONL file, but no executable contract proved that the artifact
  contained the required resource and span attributes before a collector handoff.
- Variant: add `ops/references/mcp_otel_collector_handoff.json` plus
  `ops/scripts/mcp_otel_collector_handoff.py` to validate the real OTLP JSONL
  file against an operator-owned handoff contract.
- Primary KPI: the real MCP smoke OTLP artifact validates with `status=pass`
  and `span_count=3`.
- Guardrail: live collector runtime, endpoint credentials, retention, sampling,
  and retry policy remain future-scoped/operator-owned.
- Decision rule: adopt only if focused tests pass, the real MCP smoke writes
  OTLP evidence, the handoff validator passes against that file, and the
  completion audit still avoids claiming global objective completion.

## Adopted Variant

Adopted. The collector handoff contract is now executable and source-backed.

- Manifest: `ops/references/mcp_otel_collector_handoff.json`
- Validator: `ops/scripts/mcp_otel_collector_handoff.py`
- Tests: `tests/test_mcp_otel_collector_handoff.py`
- Generated JSON: `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json`
- Generated Markdown: `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`

## Verification

- `python -m pytest tests\test_mcp_otel_collector_handoff.py -q -p no:cacheprovider`
  - `4 passed`
- `python -m py_compile ops\scripts\mcp_otel_collector_handoff.py`
  - passed
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-otel-handoff-2026-06-05.json --mcp-trace-out var\workspace-smoke-mcp-otel-handoff-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-mcp-otel-handoff-2026-06-05.otlp.jsonl`
  - `3/3 PASS`
  - `duration_seconds=121.183`
  - MCP trace `3` checks, `3` passed
- `python ops\scripts\mcp_otel_collector_handoff.py --otel-jsonl var\workspace-smoke-mcp-otel-handoff-2026-06-05.otlp.jsonl --json-out docs\reports\2026-06\MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - validator status `pass`
  - `line_count=1`
  - `resource_span_count=1`
  - `scope_span_count=1`
  - `span_count=3`
  - required resource attributes present: `4/4`
  - required span attributes present across all spans: `8/8`
- `python -m pytest tests\test_mcp_otel_collector_handoff.py tests\test_workspace_smoke.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `40 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `52 passed`
- `python -m py_compile ops\scripts\mcp_otel_collector_handoff.py ops\scripts\run_workspace_smoke.py ops\scripts\github_modernization_radar.py ops\scripts\autoresearch_completion_audit.py`
  - passed
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-otel-handoff-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - valid for `10` sources: `adopted=1`, `partially_adopted=9`, `watch=0`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OTEL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OTEL_HANDOFF_2026-06-05.md`
  - valid for `10` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Remaining Boundary

Live OpenTelemetry SDK or collector shipping remains future-scoped and
operator-owned. The unresolved decisions are collector distribution/deployment
target, OTLP endpoint and credentials, retention, sampling/processor policy,
and failure/retry handling.
