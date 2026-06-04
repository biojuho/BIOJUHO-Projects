# AutoResearch Dev-Server MCP Runtime - 2026-06-04

## Source-Backed Candidate

- Source: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
- Source pattern: MCP tools for local dev-server status, start, stop, logs, and operator-facing process visibility.
- Local constraint: process-control tools must not be exposed as silently enabled mutations.

## A/B Runtime

- Baseline: the repo had a checked MCP tool contract, but the runtime status remained contract-only.
- Variant: add a no-dependency stdio JSON-RPC runtime at `ops/scripts/dev_server_mcp_runtime.py`.
- Primary KPI: `tools/list` exposes the same four contract tools and the read-only status tool returns the existing manifest readiness schema.
- Guardrails: `start_server` and `stop_server` return `process_mutation_disabled` unless `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true` is set; tests do not launch real servers.
- Decision: adopted. This closes the local live-runtime gap for read-only operator flows while keeping process mutation explicitly gated.

## Adopted Changes

- Added `ops/scripts/dev_server_mcp_runtime.py`.
- Updated `ops/scripts/dev_server_mcp_contract.py` so runtime status is `local_stdio_runtime`.
- Added `tests/test_dev_server_mcp_runtime.py`.
- Updated `tests/test_dev_server_mcp_contract.py`.
- Regenerated:
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
- Updated `docs/guides/dev-server-control.md` with runtime and smoke instructions.

## Verification

- `python -m pytest tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py -q -p no:cacheprovider`
  - `8 passed`
- `python -m pytest tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_status.py tests\test_dev_server_control.py tests\test_github_modernization_radar.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `38 passed`
- `python -m py_compile ops\scripts\dev_server_mcp_contract.py ops\scripts\dev_server_mcp_runtime.py`
  - passed
- `'{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python ops\scripts\dev_server_mcp_runtime.py --once`
  - returned the four checked tools: `get_devserver_statuses`, `start_server`, `stop_server`, and `get_devserver_logs`
- `python ops\scripts\dev_server_mcp_contract.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
  - valid
  - `4` tools
  - `7` targets
  - runtime status `local_stdio_runtime`

## Remaining Gap

Full TUI exposure and non-local authentication policy remain future-scoped. The local runtime is intentionally stdio-only and keeps process mutation opt-in.
