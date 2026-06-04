# AutoResearch Dev-Server MCP Subprocess Smoke - 2026-06-04

## Source-Backed Candidate

- Source: `modelcontextprotocol/inspector` (`https://github.com/modelcontextprotocol/inspector`)
  - Pattern: CLI mode can list tools and call tools for automation and CI feedback loops.
- Source: `f/mcptools` (`https://github.com/f/mcptools`)
  - Pattern: stdio transport uses JSON-RPC over stdin/stdout and supports machine-readable output.
- Source: `apify/mcpc` (`https://github.com/apify/mcpc`)
  - Pattern: agent-facing CLI workflows use `tools-list`, `tools-call`, JSON output, and schema validation to catch breaking changes.

## A/B Smoke

- Baseline: the runtime had unit tests and a manual PowerShell `tools/list` pipe smoke, but no repo-owned subprocess smoke artifact.
- Variant: add `ops/scripts/dev_server_mcp_runtime_smoke.py`, which launches `ops/scripts/dev_server_mcp_runtime.py` as a subprocess and sends four JSON-RPC requests through stdio:
  - `initialize`
  - `tools/list`
  - `tools/call` for `start_server`, expected to return `process_mutation_disabled`
  - `tools/call` for `get_devserver_logs`, expected to succeed without process mutation
- Primary KPI: the smoke proves the executable runtime exposes the four checked tools and preserves the mutation guard.
- Guardrails: no real dev server is started; process mutation remains disabled by default.
- Decision: adopted.

## Adopted Changes

- Added `ops/scripts/dev_server_mcp_runtime_smoke.py`.
- Added `tests/test_dev_server_mcp_runtime_smoke.py`.
- Generated:
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-04.md`
- Updated `ops/hooks/pre-push` so the push gate runs both the focused smoke test and the subprocess smoke script.
- Updated `docs/guides/dev-server-control.md`.
- Refreshed the GitHub modernization radar with the MCP inspection/CLI source pattern.

## Verification

- `python ops\scripts\dev_server_mcp_runtime_smoke.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-04.md`
  - valid
  - `4` requests
  - `4` tools
  - `mutation_guard=process_mutation_disabled`
- `python -m pytest tests\test_dev_server_mcp_runtime_smoke.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_contract.py -q -p no:cacheprovider`
  - `11 passed`
- `python -m py_compile ops\scripts\dev_server_mcp_runtime_smoke.py ops\scripts\dev_server_mcp_runtime.py`
  - passed

## Remaining Gap

Full visual inspector/TUI exposure remains future-scoped. The adopted variant covers CI-friendly runtime regression proof without adding a network-facing tool surface.
