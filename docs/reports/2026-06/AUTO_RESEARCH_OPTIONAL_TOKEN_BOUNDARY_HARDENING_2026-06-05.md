# AutoResearch Optional Token Boundary Hardening - 2026-06-05

## Scope

Harden the external credential live verifier after a ready-boundary execution
proved that unauthenticated GitHub source refresh can fail with API rate-limit
`403` responses.

## A/B Decision

- Baseline: optional-token boundaries with no required env were marked
  `ready_for_execution`, so `github_source_refresh_rate_limit_token` attempted a
  live GitHub refresh without `GITHUB_TOKEN` or `GH_TOKEN`.
- Variant: boundaries with `status=optional_token_absent`,
  `optional_env_any_of`, and no available optional token are marked
  `blocked_missing_optional_env`.
- Decision: adopted. The variant avoids predictable partial live artifacts and
  keeps the last complete `30/30` GitHub source snapshot authoritative until an
  operator-owned token is available.

## Result

- Default dry-run now reports `selected=5`, `ready=1`, `blocked=4`,
  `executed=0`.
- `github_source_refresh_rate_limit_token` is now
  `blocked_missing_optional_env` when no `GITHUB_TOKEN` or `GH_TOKEN` is
  available.
- Execute mode skips missing optional-token boundaries before running their
  commands and reports `missing optional token env`.

## Verification

- `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  - `6 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `117 passed`
- `python -m py_compile ops\scripts\external_credential_live_verify.py`
  - passed
- `python ops\scripts\external_credential_live_verify.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`
  - `mode=dry_run`
  - `selected=5`
  - `ready=1`
  - `blocked=4`
  - `executed=0`
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-post-optional-token-boundary-2026-06-05.json`
  - `25` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-objective-coverage-post-optional-token-boundary-2026-06-05.json`
  - `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`

## Remaining Blocker

A complete live GitHub source refresh still requires `GITHUB_TOKEN` or
`GH_TOKEN`. This hardening does not claim that external boundary complete.
