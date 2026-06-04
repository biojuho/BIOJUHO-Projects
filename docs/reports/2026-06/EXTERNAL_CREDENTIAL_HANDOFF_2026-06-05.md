# External Credential Handoff

- Status: `operator_action_required`
- Boundaries: `5`
- Missing required env names: `5`
- Secret values: not emitted; this handoff contains env names only.

## Missing Required Env

- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Boundaries

| Boundary | Status | Missing required env | Verification commands |
| --- | --- | ---: | ---: |
| `canva_oauth_and_openapi_tool_execution` | `external_auth_blocked` | `2` | `2` |
| `otel_collector_endpoint_and_credentials` | `future_scoped` | `1` | `2` |
| `telegram_notification_mcp_credentials` | `credential_gated` | `2` | `1` |
| `github_source_refresh_rate_limit_token` | `optional_token_absent` | `0` | `1` |
| `hosted_agent_runtime_credentials` | `future_scoped` | `0` | `2` |

## Operator Verification

### Canva OAuth and OpenAPI tool execution

- Boundary id: `canva_oauth_and_openapi_tool_execution`
- Owner: `operator`
- Required env: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`
- Optional env: none
- Missing required env: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`
- Claim policy: do not claim complete without real Canva user credentials, login/consent redirect evidence, and proxy authentication approval

Blocked until:
- A real Canva user completes login and consent through http://localhost:8001/auth/callback.
- Proxy authentication and tool-call authorization behavior are selected and verified.

Commands:
- `cd mcp/canva-mcp && npm run doctor:canva`
- `cd mcp/canva-mcp && npm run auth:canva`

### Live OTLP collector endpoint and credentials

- Boundary id: `otel_collector_endpoint_and_credentials`
- Owner: `operator`
- Required env: `OTEL_EXPORTER_OTLP_ENDPOINT`
- Optional env: `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE`, `OTEL_EXPORTER_OTLP_CLIENT_KEY`
- Missing required env: `OTEL_EXPORTER_OTLP_ENDPOINT`
- Claim policy: do not claim live collector shipping complete without an operator-owned OTLP endpoint and credential policy

Blocked until:
- The operator selects the collector distribution, endpoint, authentication, retention, sampling, and retry policy.

Commands:
- `python ops/scripts/run_workspace_smoke.py --scope mcp --mcp-otel-out var/mcp-smoke-live-collector.otlp.jsonl`
- `python ops/scripts/mcp_otel_collector_handoff.py --otel-jsonl var/mcp-smoke-live-collector.otlp.jsonl`

### Telegram notification MCP credentials

- Boundary id: `telegram_notification_mcp_credentials`
- Owner: `operator`
- Required env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Optional env: none
- Missing required env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Claim policy: do not claim notification delivery complete from tools/list smoke alone

Blocked until:
- Notification bot token and chat target are provided for real delivery checks.

Commands:
- `python ops/scripts/mcp_service_runtime_smoke.py`

### GitHub source-refresh token boundary

- Boundary id: `github_source_refresh_rate_limit_token`
- Owner: `operator`
- Required env: none
- Optional env: `GITHUB_TOKEN`, `GH_TOKEN`
- Missing required env: none
- Claim policy: do not claim a live source refresh complete by replacing the last complete source snapshot with a rate-limited partial artifact

Blocked until:
- A GitHub token is supplied when live source-refresh volume exceeds unauthenticated API limits.

Commands:
- `python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md`

### Hosted agent runtime and tracing credentials

- Boundary id: `hosted_agent_runtime_credentials`
- Owner: `operator`
- Required env: none
- Optional env: `OPENAI_API_KEY`, `LANGCHAIN_API_KEY`, `LOGFIRE_TOKEN`
- Missing required env: none
- Claim policy: do not claim hosted autonomous agent runtime complete without operator-owned runtime, tracing, and approval credentials

Blocked until:
- A concrete hosted agent runtime, tracing backend, approval UI, and credential owner are selected.

Commands:
- `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
- `python ops/scripts/autoresearch_completion_audit.py`
