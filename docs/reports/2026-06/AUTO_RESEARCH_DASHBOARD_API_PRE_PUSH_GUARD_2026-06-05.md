# Dashboard API Pre-Push Guard

- Date: 2026-06-05
- Scope: pre-push regression gate for the dashboard quality API
- Baseline: the dashboard operator checklist had API tests, but the real pre-push pytest bundle did not directly include `tests/test_dashboard_api.py`.
- Variant: add `tests/test_dashboard_api.py` to `ops/hooks/pre-push` and assert the hook keeps it wired.
- Primary KPI: future pushes fail before merge when `/api/quality_overview` drops the credential boundary, live plan, or operator checklist API shape used by the dashboard.
- Guardrails: hook installer check remains read-only, the dashboard API suite is deterministic, and existing credential, MCP runtime, browser smoke, completion audit, and objective coverage gates remain in place.

## Adopted Variant

Adopted. `ops/hooks/pre-push` now runs `tests/test_dashboard_api.py`, and `tests/test_pre_push_hook.py` asserts the hook keeps the dashboard API suite in the pytest bundle.

## Changed Paths

- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`

## Verification

- `python -m pytest tests\test_dashboard_api.py -q --tb=line` -> `51 passed`
- `python -m pytest tests\test_pre_push_hook.py tests\test_dashboard_api.py -q --tb=line` -> `57 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_pre_push_hook.py tests/test_autoresearch_objective_coverage.py tests/test_autoresearch_completion_audit.py tests/test_dashboard_api.py tests/test_mcp_service_runtime_smoke.py tests/test_mcp_otel_collector_handoff.py tests/test_external_credential_boundary_audit.py tests/test_external_credential_handoff.py tests/test_external_credential_live_verify.py tests/test_telegram_notification_live_verify.py tests/test_agent_workflow_gate_runner.py tests/test_github_modernization_radar.py tests/test_github_source_freshness.py tests/test_canva_widget_click_smoke.py tests/test_dev_server_browser_smoke.py tests/test_dev_server_mcp_contract.py tests/test_dev_server_mcp_runtime.py tests/test_dev_server_mcp_runtime_smoke.py -q --tb=line` -> `196 passed`
- `python ops\hooks\install_hooks.py --check` -> hook current
- `python ops\scripts\autoresearch_completion_audit.py` -> `38` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py` -> `7` requirements, `cycle_prompt_covered=true`, `global_objective_complete=false`

## Remaining Boundary

This strengthens local regression protection for the dashboard quality API. It does not complete credential-gated Canva OAuth/OpenAPI execution, GitHub high-volume live refresh with a token, Telegram delivery, OTLP collector shipping, or hosted runtime/tracing operator decisions.

global_objective_complete=false
