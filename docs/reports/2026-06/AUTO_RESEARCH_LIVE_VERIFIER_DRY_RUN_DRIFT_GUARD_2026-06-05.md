# AutoResearch Live Verifier Dry-Run Drift Guard - 2026-06-05

## Scope

Protect the checked-in external credential live-verifier dry-run artifacts from
silently drifting away from the current registry and renderer.

## A/B Decision

- Baseline: pre-push executed `external_credential_live_verify.py` in dry-run
  mode, but the checked-in `EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05`
  JSON and Markdown artifacts could become stale unless manually regenerated.
- Variant: `tests/test_external_credential_live_verify.py` now compares the
  checked-in dry-run JSON and Markdown against the current verifier plan.
- Decision: adopted. The variant turns stale launch evidence into a deterministic
  test failure without executing credential-bound commands.

## Guarded Artifacts

- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`

## Verification

- `python -m pytest tests\test_external_credential_live_verify.py -q --tb=line`
  - `9 passed`
- `python -m pytest tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `26 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `120 passed`
- `python -m py_compile ops\scripts\external_credential_live_verify.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-post-live-verifier-drift-guard-2026-06-05.json`
  - `25` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-objective-coverage-post-live-verifier-drift-guard-2026-06-05.json`
  - `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`

## Completion State

The guard improves evidence quality but does not complete any external
credential boundary. `global_objective_complete` remains false.
