# AutoResearch: MCP Service Runtime Smoke

## Objective

Close the next concrete slice of the FastMCP composition gap by proving that
repo-local stdio MCP services can start, initialize, and list tools through the
real MCP protocol. This does not force a shared composition adapter or transport
switching before there is an operator-owned expansion target.

## Sources Checked

- Official MCP Python SDK: `https://github.com/modelcontextprotocol/python-sdk`
- Existing FastMCP/source-backed manifest report:
  `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_MANIFEST_2026-06-04.md`

## A/B Contract

- Baseline: the repo had a validated MCP service manifest, but runtime
  composition remained static. No shared script launched eligible stdio services
  and verified actual `initialize` plus `tools/list` behavior.
- Variant: add `ops/scripts/mcp_service_runtime_smoke.py`, which loads the
  existing service manifest, selects stdio Python MCP services, sends real MCP
  initialize/list-tools requests, validates tool counts against the manifest,
  and records credential-gated services without invoking their tools.
- Primary KPI: the real runtime smoke passes for every eligible stdio service
  and lists at least the manifest's expected minimum tools.
- Guardrail: services without stdio transport and services needing credentials
  are not forced into side-effecting tool calls.
- Decision rule: adopt only if focused tests pass, the script compiles, and the
  real runtime smoke reports `3` checked services, `3` passed services, and
  `39` listed tools.

## Adopted Variant

Adopted. Stdio MCP runtime composition readiness is now executable and
machine-readable.

- Script: `ops/scripts/mcp_service_runtime_smoke.py`
- Tests: `tests/test_mcp_service_runtime_smoke.py`
- Generated JSON:
  `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.json`
- Generated Markdown:
  `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`

## Runtime Evidence

- `dailynews-antigravity`
  - status `pass`
  - tools listed `26`
  - expected minimum tools `26`
- `desci-research`
  - status `pass`
  - tools listed `6`
  - expected minimum tools `6`
- `telegram-bot`
  - status `pass`
  - tools listed `7`
  - expected minimum tools `7`
  - missing env for tool calls:
    `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `canva-local`
  - skipped because the manifest does not declare stdio transport

## Verification

- `python -m pytest tests\test_mcp_service_runtime_smoke.py -q -p no:cacheprovider`
  - `5 passed`
- `python -m py_compile ops\scripts\mcp_service_runtime_smoke.py`
  - passed
- `python ops\scripts\mcp_service_runtime_smoke.py --json-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md --timeout 25`
  - status `pass`
  - checked services `3`
  - passed services `3`
  - skipped services `1`
  - total tools listed `39`
- `python -m pytest tests\test_mcp_service_manifest.py tests\test_mcp_service_runtime_smoke.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `17 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `57 passed`
- `python -m py_compile ops\scripts\mcp_service_runtime_smoke.py ops\scripts\mcp_service_manifest.py ops\scripts\github_modernization_radar.py ops\scripts\autoresearch_completion_audit.py ops\scripts\dev_server_mcp_runtime_smoke.py`
  - passed
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-runtime-smoke-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - valid for `11` sources: `adopted=1`, `partially_adopted=10`, `watch=0`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_MCP_RUNTIME_SMOKE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - valid for `11` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-service-runtime-smoke-2026-06-05.json --mcp-trace-out var\workspace-smoke-mcp-service-runtime-smoke-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-mcp-service-runtime-smoke-2026-06-05.otlp.jsonl`
  - `3/3 PASS`

## Remaining Boundary

Shared runtime composition adapters, transport switching, hosted TUI exposure,
and non-local MCP authentication remain future-scoped. The adopted variant
proves local stdio runtime readiness without changing operator-facing
deployment or credential boundaries.
