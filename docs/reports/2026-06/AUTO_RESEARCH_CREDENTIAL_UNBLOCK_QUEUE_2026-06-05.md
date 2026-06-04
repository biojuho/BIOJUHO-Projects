# AutoResearch Credential Unblock Queue - 2026-06-05

## Scope

This credential unblock queue cycle turns the redacted external credential
handoff from a boundary list into a prioritized operator unblock queue. The
goal is to make the next manual action obvious without storing secrets or
weakening the `global_objective_complete=false` status.

## A/B Decision

- Baseline: `EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md` listed credential
  boundaries and verification commands, but did not rank the order in which an
  operator should unblock them.
- Variant: `ops/scripts/external_credential_handoff.py` now emits an
  `unblock_queue` in JSON and a `Prioritized Unblock Queue` table in Markdown.
- Decision rule: adopt only if the queue is deterministic, redacted, generated
  from `ops/references/external_credential_boundaries.json`, and covered by a
  regression test that keeps immediate operator actions ahead of future-scoped
  runtime choices.
- Result: adopted.

## Queue

| Rank | Boundary | Operator action |
| ---: | --- | --- |
| `1` | `canva_oauth_and_openapi_tool_execution` | Provide `CANVA_CLIENT_ID` and `CANVA_CLIENT_SECRET`, complete real Canva login/consent, then verify with `cd mcp/canva-mcp && npm run doctor:canva`. |
| `2` | `github_source_refresh_rate_limit_token` | Provide `GITHUB_TOKEN` or `GH_TOKEN`, then rerun live GitHub source freshness. |
| `3` | `telegram_notification_mcp_credentials` | Provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then run the Telegram live delivery verifier and MCP service runtime smoke. |
| `4` | `otel_collector_endpoint_and_credentials` | Provide `OTEL_EXPORTER_OTLP_ENDPOINT` and any selected OTLP auth env, then run live MCP OTLP smoke and collector handoff validation. |
| `5` | `hosted_agent_runtime_credentials` | Choose the hosted runtime/tracing/approval policy and credentials, then rerun the workflow gate. |

## Verification

- Handoff regeneration:
  `python ops\scripts\external_credential_handoff.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --env-template-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`
- Generator output:
  `external credential handoff generated: 5 boundaries, status=operator_action_required, missing_required_env=5`
- Handoff tests:
  `python -m pytest tests\test_external_credential_handoff.py -q --tb=line`
  returned `6 passed`.
- Focused credential/completion suite:
  `python -m pytest tests\test_external_credential_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  returned `33 passed` after rebasing over the completion-summary drift guard.
- Pre-push pytest bundle:
  `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  returned `127 passed` after rebasing over the completion-summary,
  objective-coverage, and GitHub source-snapshot drift guards.
- Compile check:
  `python -m py_compile ops\scripts\external_credential_handoff.py` passed.
- Push-hook runtime probes:
  handoff drift check passed, live verifier dry-run passed with
  `selected=5`, `ready=1`, `blocked=4`, `executed=0`, objective coverage
  passed with `7` requirements, dev-server MCP runtime smoke passed with
  `5` requests and `5` tools, MCP service runtime smoke passed with
  `3` services and `39` tools, and the workflow dry-run/safety/matrix probes
  passed.
- Rebased completion audit:
  after rebasing over the completion-summary and objective-coverage drift guard
  commits, the completion audit reports `28` criteria with
  `global_objective_complete=false`.

## Remaining Blockers

Completion remains intentionally false until the operator supplies or approves
the external boundaries: Canva OAuth/proxy approval, GitHub token, Telegram
bot/chat credentials, live OTLP endpoint/credential policy, and hosted
runtime/tracing/approval credentials. The queue is an unblock artifact, not a
claim that those live systems are complete.

`global_objective_complete=false`
