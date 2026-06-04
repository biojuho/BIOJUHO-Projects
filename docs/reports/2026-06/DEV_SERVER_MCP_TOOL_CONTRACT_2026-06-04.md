# Dev-Server MCP Tool Contract

- Generated at: `2026-06-04T12:24:55.153978+00:00`
- Source: `Uninen/devserver-mcp` (https://github.com/Uninen/devserver-mcp)
- Runtime status: `contract_only`
- Targets: `7`
- Tools: `4`
- Read-only tools: `2`
- Process-mutating tools: `2`

## Tools

### get_devserver_statuses

- Safety: `read_only`
- Required inputs: `none`
- Command template: `python ops/scripts/dev_server_status.py --format json`
- Output contract: dev_server_status schema_version=1 JSON report

### start_server

- Safety: `process_mutating`
- Required inputs: `target_id`
- Command template: `python ops/scripts/dev_server_control.py start --target {target_id}`
- Output contract: dev_server_control start JSON state when --json-out is supplied

### stop_server

- Safety: `process_mutating`
- Required inputs: `target_id`
- Command template: `python ops/scripts/dev_server_control.py stop --target {target_id}`
- Output contract: dev_server_control stop JSON state when --json-out is supplied

### get_devserver_logs

- Safety: `read_only`
- Required inputs: `target_id`
- Command template: `python ops/scripts/dev_server_control.py tail --target {target_id}`
- Output contract: dev_server_control tail JSON logs when --json-out is supplied

## Targets

- `dashboard-api`: Workspace Dashboard API (dashboard/api)
- `dashboard-frontend`: Workspace Dashboard Frontend (dashboard/frontend)
- `agriguard-api`: AgriGuard API (agriguard/api)
- `agriguard-frontend`: AgriGuard Frontend (agriguard/frontend)
- `desci-api`: DeSci API (desci/api)
- `desci-frontend`: DeSci Frontend (desci/frontend)
- `canva-widget-preview`: Canva Widget Preview (canva-mcp/frontend)

## Boundary

This is a deterministic contract for future MCP exposure. It does not start a live MCP server by itself.
