# AutoResearch Hook Installer Check Mode - 2026-06-05

## Change

The hook installer now supports a real read-only `--check` mode. This prevents stale bootstrap hooks from rewriting `D:\AI project\.git\hooks\pre-push` while Git is still executing that same file.

Normal install mode still copies tracked hooks from `ops/hooks/` into Git's common hooks directory and normalizes line endings to LF.

## Guardrails

- `python ops/hooks/install_hooks.py --check` compares installed hooks to tracked templates and returns nonzero on missing or stale hooks.
- `python ops/hooks/install_hooks.py` remains the explicit write path.
- `tests/test_pre_push_hook.py` asserts that executable installer calls in `ops/hooks/pre-push` use read-only `--check`, preventing hook self-mutation from coming back.
- `tests/test_pre_push_hook.py` verifies check mode does not overwrite a stale destination hook.
- `ops/hooks/pre-push` now includes `tests/test_pre_push_hook.py` in its pytest bundle.

## Verification

- `python -m pytest tests\test_pre_push_hook.py -q --tb=line`: `6 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`: `115 passed`
- `python -m py_compile ops\hooks\install_hooks.py`: passed
- `python ops\hooks\install_hooks.py --check`: `[ok] pre-push is current`; `1 hook(s) checked.`
- `python ops\hooks\install_hooks.py`: installed `pre-push` to `D:\AI project\.git\hooks\pre-push`
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-post-hook-check-mode-prepush-2026-06-05.json`: `25` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`

## Completion State

This closes the hook self-mutation failure observed during push validation. It does not change the broader launch completion state: external credentials and hosted/runtime approvals remain operator-owned blockers.
