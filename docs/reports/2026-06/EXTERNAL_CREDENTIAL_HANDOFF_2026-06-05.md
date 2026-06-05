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

## Prioritized Unblock Queue

| Rank | Boundary | Operator action | Env names | Verify after unblock |
| ---: | --- | --- | --- | --- |
| `1` | `canva_oauth_and_openapi_tool_execution` | Set required env and complete operator approval: A real Canva user completes login and consent through http://localhost:8001/auth/callback; Proxy authentication and tool-call authorization behavior are selected and verified | `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET` | `cd mcp/canva-mcp && npm run doctor:canva`<br>`cd mcp/canva-mcp && npm run auth:canva` |
| `2` | `github_source_refresh_rate_limit_token` | Set one optional token/env value, then rerun verification: GITHUB_TOKEN, GH_TOKEN | `GITHUB_TOKEN`, `GH_TOKEN` | `python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md` |
| `3` | `telegram_notification_mcp_credentials` | Set required env and complete operator approval: Notification bot token and chat target are provided for real delivery checks | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `python ops/scripts/telegram_notification_live_verify.py --execute --json-out var/telegram-notification-live-verify.json --markdown-out var/telegram-notification-live-verify.md`<br>`python ops/scripts/mcp_service_runtime_smoke.py` |
| `4` | `otel_collector_endpoint_and_credentials` | Set required env and complete operator approval: The operator selects the collector distribution, endpoint, authentication, retention, sampling, and retry policy | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE`, `OTEL_EXPORTER_OTLP_CLIENT_KEY` | `python ops/scripts/run_workspace_smoke.py --scope mcp --mcp-otel-out var/mcp-smoke-live-collector.otlp.jsonl`<br>`python ops/scripts/mcp_otel_collector_handoff.py --otel-jsonl var/mcp-smoke-live-collector.otlp.jsonl` |
| `5` | `hosted_agent_runtime_credentials` | Set operator approval marker after runtime/policy decision: HOSTED_AGENT_RUNTIME_APPROVED | `OPENAI_API_KEY`, `LANGCHAIN_API_KEY`, `LOGFIRE_TOKEN`, `HOSTED_AGENT_RUNTIME_APPROVED` | `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`<br>`python ops/scripts/autoresearch_completion_audit.py` |

## Boundaries

| Boundary | Status | Missing required env | Verification commands |
| --- | --- | ---: | ---: |
| `canva_oauth_and_openapi_tool_execution` | `external_auth_blocked` | `2` | `2` |
| `otel_collector_endpoint_and_credentials` | `future_scoped` | `1` | `2` |
| `telegram_notification_mcp_credentials` | `credential_gated` | `2` | `2` |
| `github_source_refresh_rate_limit_token` | `optional_token_absent` | `0` | `1` |
| `hosted_agent_runtime_credentials` | `future_scoped` | `0` | `2` |

## Operator Verification

### Canva OAuth and OpenAPI tool execution

- Boundary id: `canva_oauth_and_openapi_tool_execution`
- Owner: `operator`
- Required env: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`
- Optional env: none
- Missing required env: `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`
- Consent items: `0`
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
- Consent items: `0`
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
- Consent items: `0`
- Claim policy: do not claim notification delivery complete from tools/list smoke alone

Blocked until:
- Notification bot token and chat target are provided for real delivery checks.

Commands:
- `python ops/scripts/telegram_notification_live_verify.py --execute --json-out var/telegram-notification-live-verify.json --markdown-out var/telegram-notification-live-verify.md`
- `python ops/scripts/mcp_service_runtime_smoke.py`

### GitHub source-refresh token boundary

- Boundary id: `github_source_refresh_rate_limit_token`
- Owner: `operator`
- Required env: none
- Optional env: `GITHUB_TOKEN`, `GH_TOKEN`
- Missing required env: none
- Consent items: `0`
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
- Consent items: `2`
- Claim policy: do not claim hosted autonomous agent runtime complete without operator-owned runtime, tracing, approval credentials, and HOSTED_AGENT_RUNTIME_APPROVED=true

Blocked until:
- A concrete hosted agent runtime, tracing backend, approval UI, and credential owner are selected.
- HOSTED_AGENT_RUNTIME_APPROVED=true is set only after the operator confirms the hosted runtime consent and approval policy.

Consent items:
- `hosted_agent_toolbox_mcp` (`mcp_toolbox`): Review and approve hosted toolbox MCP tool access before setting HOSTED_AGENT_RUNTIME_APPROVED=true.
- `hosted_agent_tracing_runtime` (`runtime_tracing`): Confirm hosted runtime and tracing backend policy before live execution.

Commands:
- `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
- `python ops/scripts/autoresearch_completion_audit.py`
