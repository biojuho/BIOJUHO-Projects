# Dev-Server MCP Tool Contract

- Generated at: `2026-06-04T15:14:56.435415+00:00`
- Source: `Uninen/devserver-mcp` (https://github.com/Uninen/devserver-mcp)
- Runtime status: `local_stdio_runtime`
- Targets: `7`
- Tools: `5`
- Read-only tools: `3`
- Process-mutating tools: `2`

## Tools

### get_devserver_statuses

- Safety: `read_only`
- Required inputs: `none`
- Command template: `python ops/scripts/dev_server_status.py --format json`
- Output contract: dev_server_status schema_version=1 JSON report

### get_devserver_policy

- Safety: `read_only`
- Required inputs: `none`
- Command template: `python ops/scripts/dev_server_mcp_runtime.py --policy`
- Output contract: operator_policy schema_version=1 JSON policy

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

## Operator Policy

- Transport: `stdio`
- Network exposure: `none`
- Non-local control: `unsupported`
- Process mutation default: `disabled`

## Boundary

A local stdio runtime is available at `python ops/scripts/dev_server_mcp_runtime.py`.
Read-only status, policy, and log tools are enabled by default. Process-mutating start/stop tools require `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true` in the local environment.
