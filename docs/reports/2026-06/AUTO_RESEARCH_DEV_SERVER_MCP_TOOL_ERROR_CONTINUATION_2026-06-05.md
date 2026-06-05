# AutoResearch Dev-Server MCP Tool Error Continuation

## Objective

Adopt the Google ADK MCP tool-error continuity signal in the local dev-server
MCP runtime proof so a tool failure cannot silently become a session-drop risk.

## Source Signal

- Repository: `google/adk-python`
- Release page: `https://github.com/google/adk-python/releases/tag/v2.1.0`
- Source commit: `https://github.com/google/adk-python/commit/933653c`
- Upstream signal: `tools: Prevent session drop on MCP tool error`
- Local mapping: prove the local stdio runtime keeps serving the same process
  after an MCP tool error by sending another successful request in sequence.

## A/B Contract

- Baseline: `dev_server_mcp_runtime_smoke.py` already proved a guarded
  `start_server` MCP tool error did not stop a following read-only log request,
  but the artifact did not explicitly exercise an unknown tool error or record a
  post-error continuation field.
- Variant: add an explicit `missing_tool` request to the subprocess smoke, assert
  it returns `isError=true` with `status=unknown_tool`, and then require
  `get_devserver_logs` to succeed afterward in the same stdio runtime.
- Primary KPI: the durable smoke artifact records `unknown_tool_error_status`
  and `post_error_logs_target_id` with a passing status.
- Guardrails: tool list, policy, mutation guard, process return code, stderr, and
  JSON-RPC id ordering all remain validated.
- Decision: adopted. The variant makes session continuation after MCP tool
  errors explicit in both tests and repo-owned smoke evidence.

## Changed Files

- `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - Adds an explicit unknown tool request before the final log request.
  - Validates the unknown tool MCP error and post-error log success.
  - Records `unknown_tool_error_status` and `post_error_logs_target_id`.
- `tests/test_dev_server_mcp_runtime.py`
  - Adds `test_tool_error_does_not_drop_mcp_session`.
- `tests/test_dev_server_mcp_runtime_smoke.py`
  - Updates the subprocess smoke expectations to `6` requests and the new
    continuation summary fields.
- `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json`
  - Regenerated with `request_count=6`, `response_count=6`, and no errors.
- `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - Regenerated with the unknown-tool and post-error log evidence.

## Verification

- `python -m pytest tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `10 passed`
- `python ops\scripts\dev_server_mcp_runtime_smoke.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - `6 requests`
  - `5 tools`
  - `mutation_guard=process_mutation_disabled`
  - `unknown_tool_error_status=unknown_tool`
  - `post_error_logs_target_id=dashboard-api`
- `current_tip_freshness_gate`
  - proof baseline: `d9b72a3`
  - allowed post-proof paths include the dev-server MCP runtime smoke script,
    runtime tests, smoke tests, and this report.
- `protected_path_freshness`
  - no changed launch-critical browser/app protected paths after proof.
- `global_objective_complete=false`

## Remaining Boundary

This cycle hardens local MCP runtime continuity evidence only. Operator-owned
credential and hosted-runtime blockers remain outside this local proof.
