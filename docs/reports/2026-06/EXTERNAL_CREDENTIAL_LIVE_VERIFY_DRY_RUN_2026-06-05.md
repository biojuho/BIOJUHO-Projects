# External Credential Live Verifier

- Status: `pass`
- Mode: `dry_run`
- Selection: `selected`
- Plan order: `unblock_queue`
- Selected boundaries: `5`
- Ready boundaries: `0`
- Blocked boundaries: `5`
- Next unblock: `canva_oauth_and_openapi_tool_execution` (rank `1`, env: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, consent: `none`)
- Commands planned: `9`
- Commands executed: `0`

## Boundaries

| Rank | Boundary | Live status | Missing required env | Consent items | Trace providers | Commands |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| `1` | `canva_oauth_and_openapi_tool_execution` | `blocked_missing_required_env` | `2` | `0` | `0` | `2` |
| `2` | `github_source_refresh_rate_limit_token` | `blocked_missing_optional_env` | `0` | `0` | `0` | `1` |
| `3` | `telegram_notification_mcp_credentials` | `blocked_missing_required_env` | `2` | `0` | `0` | `2` |
| `4` | `otel_collector_endpoint_and_credentials` | `blocked_missing_required_env` | `1` | `0` | `0` | `2` |
| `5` | `hosted_agent_runtime_credentials` | `blocked_operator_approval` | `0` | `2` | `4` | `2` |

## Operator Consent Items

### Hosted agent runtime and tracing credentials

- `hosted_agent_toolbox_mcp` (`mcp_toolbox`): Review and approve hosted toolbox MCP tool access before setting HOSTED_AGENT_RUNTIME_APPROVED=true.
- `hosted_agent_tracing_runtime` (`runtime_tracing`): Confirm hosted runtime and tracing backend policy before live execution.


## Trace Processor Providers

### Hosted agent runtime and tracing credentials

- `openai_traces` (`OPENAI_API_KEY`): OpenAI Traces
- `langsmith` (`LANGCHAIN_API_KEY`): LangSmith
- `pydantic_logfire` (`LOGFIRE_TOKEN`): Pydantic Logfire
- `latitude` (`LATITUDE_API_KEY`): Latitude


## Commands

### canva_oauth_and_openapi_tool_execution

- Status: `planned`
- Command: `cd mcp/canva-mcp && npm run doctor:canva`

### canva_oauth_and_openapi_tool_execution

- Status: `planned`
- Command: `cd mcp/canva-mcp && npm run auth:canva`

### github_source_refresh_rate_limit_token

- Status: `planned`
- Command: `python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md`

### telegram_notification_mcp_credentials

- Status: `planned`
- Command: `python ops/scripts/telegram_notification_live_verify.py --execute --json-out var/telegram-notification-live-verify.json --markdown-out var/telegram-notification-live-verify.md`

### telegram_notification_mcp_credentials

- Status: `planned`
- Command: `python ops/scripts/mcp_service_runtime_smoke.py`

### otel_collector_endpoint_and_credentials

- Status: `planned`
- Command: `python ops/scripts/run_workspace_smoke.py --scope mcp --mcp-otel-out var/mcp-smoke-live-collector.otlp.jsonl`

### otel_collector_endpoint_and_credentials

- Status: `planned`
- Command: `python ops/scripts/mcp_otel_collector_handoff.py --otel-jsonl var/mcp-smoke-live-collector.otlp.jsonl`

### hosted_agent_runtime_credentials

- Status: `planned`
- Command: `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`

### hosted_agent_runtime_credentials

- Status: `planned`
- Command: `python ops/scripts/autoresearch_completion_audit.py`

## Errors

- none
