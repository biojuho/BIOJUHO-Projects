# AutoResearch Dev-Server MCP Policy Tool - 2026-06-05

## Objective

Make the dev-server MCP runtime's access and mutation boundary directly
queryable by agents and operators before they attempt a process-mutating tool
call.

## Source-Backed Candidate

- Source A: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
  - Pattern: MCP tools expose status, logs, start, and stop for local
    development servers.
- Source B: `microsoft/mcp-gateway`
  (`https://github.com/microsoft/mcp-gateway`)
  - Pattern: MCP server routing, authorization, lifecycle management, and
    observability policy are first-class gateway concerns before widening
    server exposure.

## A/B Contract

- Baseline: process mutation policy was only visible indirectly when
  `start_server` or `stop_server` returned `process_mutation_disabled`.
- Variant: add a read-only `get_devserver_policy` tool and `--policy` CLI
  output that report runtime status, stdio transport, no network exposure,
  local-only operation, unsupported non-local control, read-only tools,
  process-mutating tools, and the opt-in mutation env var.
- Primary KPI: the subprocess smoke proves `tools/list` exposes `5` tools and
  `tools/call get_devserver_policy` succeeds without process mutation.
- Guardrails: start/stop remain process-mutating and still return
  `process_mutation_disabled` unless
  `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true`; no real dev server is started.

## Adopted Changes

- `ops/scripts/dev_server_mcp_contract.py`
  - Added `get_devserver_policy`, `operator_policy`, and the
    `microsoft/mcp-gateway` companion source pattern.
- `ops/scripts/dev_server_mcp_runtime.py`
  - Added `tools/call get_devserver_policy` and `--policy`.
- `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - Extended the real stdio smoke from `4` to `5` requests and tools.
- `docs/guides/dev-server-control.md`
  - Documented policy inspection and non-local-control boundary.
- Generated evidence:
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`

## Verification

- `python -m pytest tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `12 passed`
- `python ops\scripts\dev_server_mcp_contract.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.md`
  - valid
  - `5` tools
  - `7` targets
- `python ops\scripts\dev_server_mcp_runtime_smoke.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - valid
  - `5` requests
  - `5` tools
  - `mutation_guard=process_mutation_disabled`
- `python ops\scripts\dev_server_mcp_runtime.py --policy`
  - reported `runtime_status=local_stdio_runtime`
  - reported `network_exposure=none`
  - reported `non_local_control.status=unsupported`
  - reported `process_mutation.default=disabled`

## Decision

Adopted. This narrows the dev-server MCP non-local auth/policy gap by making
the current local-only boundary machine-readable and smoke-tested. Full TUI
exposure or a network-facing gateway remains future-scoped until an
operator-owned authentication policy is supplied.
