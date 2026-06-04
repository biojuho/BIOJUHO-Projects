# AutoResearch Live Verifier Unblock Order - 2026-06-05

## Scope

This live verifier unblock order cycle aligns the dry-run live verifier with
the same operator priority already used by the redacted handoff Markdown and
env template.

## A/B Decision

- Baseline: `external_credential_live_verify.py` planned default dry-run
  boundaries in registry order. The dry-run report showed OTLP collector and
  hosted runtime checks before the GitHub token and Telegram checks, which
  contradicted the operator unblock queue.
- Variant: default live-verifier planning now sorts boundaries by unblock
  priority and records `plan_order=unblock_queue`; explicit `--boundary`
  selections still preserve the caller's order.
- Decision rule: adopt only if checked-in dry-run artifacts update
  deterministically, ready-only behavior remains unchanged, and the
  credential/completion guardrail suite stays green.
- Result: adopted.

## Queue Order

Default dry-run planning now orders boundaries as:

1. `canva_oauth_and_openapi_tool_execution`
2. `github_source_refresh_rate_limit_token`
3. `telegram_notification_mcp_credentials`
4. `otel_collector_endpoint_and_credentials`
5. `hosted_agent_runtime_credentials`

The report remains redacted and still reports `ready=1`, `blocked=4`, and
`executed=0` without external credentials.

## Verification

- Live-verifier tests:
  `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  returned `11 passed`.
- Focused credential/completion suite:
  `python -m pytest tests\test_external_credential_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  returned `35 passed` after regenerating the checked-in completion audit
  summary artifact.
- Pre-push pytest bundle:
  `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  returned `130 passed`.
- Dry-run regeneration:
  `python ops\scripts\external_credential_live_verify.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`
  updated the checked-in `plan_order`, Markdown plan-order line, and rank
  evidence.
- Ready-only regeneration:
  `python ops\scripts\external_credential_live_verify.py --ready-only --execute --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md`
  preserved `selected=1`, `ready=1`, `blocked=0`, and `executed=2`.

Completion remains blocked on external operator credentials and approvals;
this is an ordering and evidence hardening slice only.

`global_objective_complete=false`
