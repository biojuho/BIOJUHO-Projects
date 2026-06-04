# AutoResearch Ready-Only Credential Execution - 2026-06-05

## Scope

Add an operator-friendly live verifier mode that executes only boundaries that
are currently ready, without manually listing boundary IDs and without running
known credential-blocked commands.

## A/B Decision

- Baseline: operators had to pass explicit `--boundary` arguments to execute
  only runnable checks. Running all boundaries in execute mode correctly failed
  on skipped credential blockers.
- Variant: `--ready-only` filters the verified plan to boundaries whose
  `live_status` is `ready_for_execution`.
- Decision: adopted. The variant reduces operator error while preserving the
  rule that blocked credential boundaries are not claimed complete.

## Result

- `python ops\scripts\external_credential_live_verify.py --ready-only --execute --timeout-seconds 180 --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md`
  - `mode=execute`
  - `selected=1`
  - `ready=1`
  - `blocked=0`
  - `executed=2`

## Evidence

- JSON: `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json`
- Markdown: `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md`

## Verification

- `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  - `8 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `119 passed`
- `python -m py_compile ops\scripts\external_credential_live_verify.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-post-ready-only-credential-2026-06-05.json`
  - `25` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-objective-coverage-post-ready-only-credential-2026-06-05.json`
  - `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`

## Remaining Blocker

Ready-only execution does not complete Canva OAuth, live OTLP collector,
GitHub token-backed source refresh, Telegram delivery, or hosted runtime
credential ownership. Those remain explicit external boundaries.
