# AutoResearch: Browser QA Freshness Gate

## Objective

Prevent stale direct browser/app-click evidence from satisfying the completion
audit after launch-critical app or browser-smoke paths change.

## A/B Contract

- Baseline: `direct_app_click_qa` validated existing browser proof artifacts
  and required text, but it did not detect later changes under dashboard,
  DeSci, AgriGuard, Canva widget preview, or browser-smoke definitions.
- Variant: add `protected_path_freshness` evidence validation to
  `autoresearch_completion_audit.py`. The new guard checks that a browser proof
  baseline commit is an ancestor of the active remote ref and rejects any
  changed protected path after that baseline.
- Primary KPI: completion audit remains valid when no protected browser/app
  path changed after the proof baseline, and focused tests reject a changed
  browser surface.
- Guardrail: unrelated docs, report, or ops evidence changes must remain
  allowed without requiring fresh browser clicks.
- Decision rule: adopt only if focused tests cover both pass and fail paths,
  the real protected-path diff is empty, and the expanded pre-push-equivalent
  suite passes.

## Adopted Variant

Adopted. The completion contract now includes required
`direct_browser_qa_freshness_gate` evidence using proof baseline `f53eb69`
against `origin/feat/observability-gateway-2026-05`.

Protected paths:

- `apps/dashboard/`
- `apps/desci-platform/`
- `apps/AgriGuard/`
- `mcp/canva-mcp/`
- `ops/references/dev_server_targets.json`
- `ops/references/dev_server_browser_checks.json`
- `ops/scripts/dev_server_browser_smoke.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `tests/test_dev_server_browser_smoke.py`
- `tests/test_desci_browser_smoke.py`

## Runtime Evidence

- `git diff --name-only f53eb69..origin/feat/observability-gateway-2026-05 -- apps/dashboard apps/desci-platform apps/AgriGuard mcp/canva-mcp ops/references/dev_server_targets.json ops/references/dev_server_browser_checks.json ops/scripts/dev_server_browser_smoke.py tests/test_dev_server_browser_smoke.py tests/test_desci_browser_smoke.py`
  - no changed protected paths
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_BROWSER_QA_FRESHNESS_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_BROWSER_QA_FRESHNESS_2026-06-05.md`
  - `18` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Verification

- `python -m pytest tests\test_autoresearch_completion_audit.py -q`
  - `8 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_autoresearch_completion_audit.py tests/test_mcp_service_runtime_smoke.py tests/test_mcp_otel_collector_handoff.py tests/test_agent_workflow_gate_runner.py tests/test_github_source_freshness.py tests/test_dev_server_browser_smoke.py tests/test_dev_server_mcp_contract.py tests/test_dev_server_mcp_runtime.py tests/test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `80 passed`
- Hook runtime probes:
  - dev-server MCP runtime smoke: `5` requests, `5` tools
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - single workflow dry-run selected `1`
  - side-effect safety execute selected `1` and skipped `1`
  - matrix dry-run covered `6` workflows and `6` selected gates
- `python -m py_compile ops\scripts\autoresearch_completion_audit.py`
  - passed

## Decision

The variant is adopted as browser evidence infrastructure. It does not replace
real browser/app-click QA; it forces fresh browser proof when launch-critical
browser surfaces change.
