# AutoResearch Ready-Only Execution Drift Guard - 2026-06-05

## Scope

Protect the checked-in ready-only credential execution evidence from silently
drifting away from the current runnable boundary set.

## A/B Decision

- Baseline: `EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05`
  recorded a passing ready-only execution, but no deterministic test compared
  that evidence to the current verifier behavior.
- Variant: `tests/test_external_credential_live_verify.py` now re-runs
  ready-only execute mode with external credential env names removed and
  compares stable JSON fields plus deterministic Markdown against the checked-in
  evidence.
- Decision: adopted. The variant verifies that the current runnable command set
  still matches the recorded evidence while excluding volatile timestamps and
  elapsed seconds.

## Guarded Artifacts

- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md`

## Verification

- `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  - `10 passed`
- `python -m pytest tests\test_external_credential_live_verify.py tests\test_github_source_freshness.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `34 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `123 passed`
- `python -m py_compile ops\scripts\external_credential_live_verify.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-post-ready-only-drift-guard-2026-06-05.json`
  - `26` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-objective-coverage-post-ready-only-drift-guard-2026-06-05.json`
  - `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`

## Completion State

This guard improves launch evidence freshness. It does not supply Canva,
GitHub, OTLP, Telegram, or hosted runtime credentials; `global_objective_complete`
remains false.
