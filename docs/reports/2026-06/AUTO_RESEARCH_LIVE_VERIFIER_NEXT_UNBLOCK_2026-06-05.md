# AutoResearch Live Verifier Next Unblock - 2026-06-05

## Scope

This live verifier next unblock cycle makes the credential verifier name the
first operator action directly. The previous dry-run output showed counts and
ordered boundaries, but the one-line CLI result still required opening the
Markdown or JSON report to identify the next credential to provide.

## A/B Decision

- Baseline: CLI output ended at `blocked=4, executed=0`, while Markdown showed
  only the ordered boundary table.
- Variant: `external_credential_live_verify.py` now adds
  `summary.next_unblock` to JSON, renders `Next unblock:` in Markdown, and
  prints `next=canva_oauth_and_openapi_tool_execution` in the CLI summary.
- Decision rule: adopt only if the next unblock is derived from the same
  ordered plan, remains redacted to env names only, and ready-only execution
  reports no next unblock.
- Result: adopted.

## Evidence

- Default dry-run:
  - `next_unblock.boundary_id` is
    `canva_oauth_and_openapi_tool_execution`
  - `next_unblock.env_names` contains `CANVA_CLIENT_ID` and
    `CANVA_CLIENT_SECRET`
  - Markdown renders `Next unblock:
    canva_oauth_and_openapi_tool_execution`
- Ready-only execution:
  - `next_unblock` is `null`
  - execution remains `selected=1`, `ready=1`, `blocked=0`, and `executed=2`

## Verification

- Live-verifier tests:
  `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  returned `11 passed`.
- Focused credential/completion suite:
  `python -m pytest tests\test_external_credential_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  returned `35 passed`.
- Pre-push pytest bundle:
  `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  returned `130 passed`.

Completion remains blocked on external operator credentials and approvals;
this is an operator-readiness improvement only.

`global_objective_complete=false`
