# External Credential Boundary Audit

- Status: `pass`
- Boundaries: `5`
- Status counts: `credential_gated=1, external_auth_blocked=1, future_scoped=2, optional_token_absent=1`
- Missing required env names: `5`

## Boundaries

| Boundary | Status | Required env missing | Optional env available | Consent items | Evidence paths | Verification commands |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| `canva_oauth_and_openapi_tool_execution` | `external_auth_blocked` | `2` | `false` | `0` | `2` | `2` |
| `otel_collector_endpoint_and_credentials` | `future_scoped` | `1` | `false` | `0` | `1` | `2` |
| `hosted_agent_runtime_credentials` | `future_scoped` | `0` | `false` | `2` | `1` | `2` |
| `github_source_refresh_rate_limit_token` | `optional_token_absent` | `0` | `false` | `0` | `1` | `1` |
| `telegram_notification_mcp_credentials` | `credential_gated` | `2` | `false` | `0` | `2` | `2` |

## Missing Required Env

- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Claim Policies

### canva_oauth_and_openapi_tool_execution

- Owner: `operator`
- Policy: do not claim complete without real Canva user credentials, login/consent redirect evidence, and proxy authentication approval
- Blocked until: A real Canva user completes login and consent through http://localhost:8001/auth/callback.; Proxy authentication and tool-call authorization behavior are selected and verified.
- Consent items: `0`

### otel_collector_endpoint_and_credentials

- Owner: `operator`
- Policy: do not claim live collector shipping complete without an operator-owned OTLP endpoint and credential policy
- Blocked until: The operator selects the collector distribution, endpoint, authentication, retention, sampling, and retry policy.
- Consent items: `0`

### hosted_agent_runtime_credentials

- Owner: `operator`
- Policy: do not claim hosted autonomous agent runtime complete without operator-owned runtime, tracing, approval credentials, and HOSTED_AGENT_RUNTIME_APPROVED=true
- Blocked until: A concrete hosted agent runtime, tracing backend, approval UI, and credential owner are selected.; HOSTED_AGENT_RUNTIME_APPROVED=true is set only after the operator confirms the hosted runtime consent and approval policy.
- Consent items: `2`

### github_source_refresh_rate_limit_token

- Owner: `operator`
- Policy: do not claim a live source refresh complete by replacing the last complete source snapshot with a rate-limited partial artifact
- Blocked until: A GitHub token is supplied when live source-refresh volume exceeds unauthenticated API limits.
- Consent items: `0`

### telegram_notification_mcp_credentials

- Owner: `operator`
- Policy: do not claim notification delivery complete from tools/list smoke alone
- Blocked until: Notification bot token and chat target are provided for real delivery checks.
- Consent items: `0`

## Errors

- none
