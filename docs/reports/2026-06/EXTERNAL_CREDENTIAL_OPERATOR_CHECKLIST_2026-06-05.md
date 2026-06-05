# External Credential Operator Checklist

- Status: `operator_action_required`
- Items: `5`
- Ready to execute: `0`
- Blocked: `5`
- Next boundary: `canva_oauth_and_openapi_tool_execution`
- Secret values: not emitted; checklist contains env names only.

## Queue

| Rank | Boundary | Live status | Ready now | Blocked reason | Env names | Commands |
| ---: | --- | --- | --- | --- | --- | ---: |
| `1` | `canva_oauth_and_openapi_tool_execution` | `blocked_missing_required_env` | `false` | missing required env: CANVA_CLIENT_ID, CANVA_CLIENT_SECRET | `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET` | `2` |
| `2` | `github_source_refresh_rate_limit_token` | `blocked_missing_optional_env` | `false` | missing optional env: GITHUB_TOKEN, GH_TOKEN | `GITHUB_TOKEN`, `GH_TOKEN` | `1` |
| `3` | `telegram_notification_mcp_credentials` | `blocked_missing_required_env` | `false` | missing required env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `2` |
| `4` | `otel_collector_endpoint_and_credentials` | `blocked_missing_required_env` | `false` | missing required env: OTEL_EXPORTER_OTLP_ENDPOINT | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE`, `OTEL_EXPORTER_OTLP_CLIENT_KEY` | `2` |
| `5` | `hosted_agent_runtime_credentials` | `blocked_operator_approval` | `false` | missing operator approval marker: HOSTED_AGENT_RUNTIME_APPROVED | `OPENAI_API_KEY`, `LANGCHAIN_API_KEY`, `LOGFIRE_TOKEN`, `LATITUDE_API_KEY`, `HOSTED_AGENT_RUNTIME_APPROVED` | `2` |

## Boundary Steps

### Canva OAuth and OpenAPI tool execution

- Boundary id: `canva_oauth_and_openapi_tool_execution`
- Registry status: `external_auth_blocked`
- Live status: `blocked_missing_required_env`
- Ready to execute: `false`
- Operator action: Set required env and complete operator approval: A real Canva user completes login and consent through http://localhost:8001/auth/callback; Proxy authentication and tool-call authorization behavior are selected and verified
- Claim policy: do not claim complete without real Canva user credentials, login/consent redirect evidence, and proxy authentication approval
- Trace processor providers: none

Checklist:
- `missing` Required env: CANVA_CLIENT_ID, CANVA_CLIENT_SECRET
- `not_blocking` Optional env: none
- `not_blocking` Operator approval: A real Canva user completes login and consent through http://localhost:8001/auth/callback; Proxy authentication and tool-call authorization behavior are selected and verified
- `ready` Operator approval marker: none required
- `ready` Operator consent items: none
- `ready` Trace processor provider choice: none
- `blocked` Verification commands: 2 command(s)

Verify after unblock:
- `cd mcp/canva-mcp && npm run doctor:canva`
- `cd mcp/canva-mcp && npm run auth:canva`

### GitHub source-refresh token boundary

- Boundary id: `github_source_refresh_rate_limit_token`
- Registry status: `optional_token_absent`
- Live status: `blocked_missing_optional_env`
- Ready to execute: `false`
- Operator action: Set one optional token/env value, then rerun verification: GITHUB_TOKEN, GH_TOKEN
- Claim policy: do not claim a live source refresh complete by replacing the last complete source snapshot with a rate-limited partial artifact
- Trace processor providers: none

Checklist:
- `ready` Required env: none required
- `blocked` Optional env: GITHUB_TOKEN, GH_TOKEN
- `not_blocking` Operator approval: A GitHub token is supplied when live source-refresh volume exceeds unauthenticated API limits
- `ready` Operator approval marker: none required
- `ready` Operator consent items: none
- `ready` Trace processor provider choice: none
- `blocked` Verification commands: 1 command(s)

Verify after unblock:
- `python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md`

### Telegram notification MCP credentials

- Boundary id: `telegram_notification_mcp_credentials`
- Registry status: `credential_gated`
- Live status: `blocked_missing_required_env`
- Ready to execute: `false`
- Operator action: Set required env and complete operator approval: Notification bot token and chat target are provided for real delivery checks
- Claim policy: do not claim notification delivery complete from tools/list smoke alone
- Trace processor providers: none

Checklist:
- `missing` Required env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- `not_blocking` Optional env: none
- `not_blocking` Operator approval: Notification bot token and chat target are provided for real delivery checks
- `ready` Operator approval marker: none required
- `ready` Operator consent items: none
- `ready` Trace processor provider choice: none
- `blocked` Verification commands: 2 command(s)

Verify after unblock:
- `python ops/scripts/telegram_notification_live_verify.py --execute --json-out var/telegram-notification-live-verify.json --markdown-out var/telegram-notification-live-verify.md`
- `python ops/scripts/mcp_service_runtime_smoke.py`

### Live OTLP collector endpoint and credentials

- Boundary id: `otel_collector_endpoint_and_credentials`
- Registry status: `future_scoped`
- Live status: `blocked_missing_required_env`
- Ready to execute: `false`
- Operator action: Set required env and complete operator approval: The operator selects the collector distribution, endpoint, authentication, retention, sampling, and retry policy
- Claim policy: do not claim live collector shipping complete without an operator-owned OTLP endpoint and credential policy
- Trace processor providers: none

Checklist:
- `missing` Required env: OTEL_EXPORTER_OTLP_ENDPOINT
- `not_blocking` Optional env: OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE, OTEL_EXPORTER_OTLP_CLIENT_KEY
- `not_blocking` Operator approval: The operator selects the collector distribution, endpoint, authentication, retention, sampling, and retry policy
- `ready` Operator approval marker: none required
- `ready` Operator consent items: none
- `ready` Trace processor provider choice: none
- `blocked` Verification commands: 2 command(s)

Verify after unblock:
- `python ops/scripts/run_workspace_smoke.py --scope mcp --mcp-otel-out var/mcp-smoke-live-collector.otlp.jsonl`
- `python ops/scripts/mcp_otel_collector_handoff.py --otel-jsonl var/mcp-smoke-live-collector.otlp.jsonl`

### Hosted agent runtime and tracing credentials

- Boundary id: `hosted_agent_runtime_credentials`
- Registry status: `future_scoped`
- Live status: `blocked_operator_approval`
- Ready to execute: `false`
- Operator action: Set operator approval marker after runtime/policy decision: HOSTED_AGENT_RUNTIME_APPROVED
- Claim policy: do not claim hosted autonomous agent runtime complete without operator-owned runtime, tracing, approval credentials, and HOSTED_AGENT_RUNTIME_APPROVED=true
- Trace processor providers: OpenAI Traces (OPENAI_API_KEY), LangSmith (LANGCHAIN_API_KEY), Pydantic Logfire (LOGFIRE_TOKEN), Latitude (LATITUDE_API_KEY)

Checklist:
- `ready` Required env: none required
- `not_blocking` Optional env: OPENAI_API_KEY, LANGCHAIN_API_KEY, LOGFIRE_TOKEN, LATITUDE_API_KEY
- `blocked` Operator approval: A concrete hosted agent runtime, tracing backend, approval UI, and credential owner are selected; HOSTED_AGENT_RUNTIME_APPROVED=true is set only after the operator confirms the hosted runtime consent and approval policy
- `blocked` Operator approval marker: HOSTED_AGENT_RUNTIME_APPROVED
- `blocked` Operator consent items: hosted_agent_toolbox_mcp, hosted_agent_tracing_runtime
- `blocked` Trace processor provider choice: OpenAI Traces (OPENAI_API_KEY), LangSmith (LANGCHAIN_API_KEY), Pydantic Logfire (LOGFIRE_TOKEN), Latitude (LATITUDE_API_KEY)
- `blocked` Verification commands: 2 command(s)

Verify after unblock:
- `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
- `python ops/scripts/autoresearch_completion_audit.py`
