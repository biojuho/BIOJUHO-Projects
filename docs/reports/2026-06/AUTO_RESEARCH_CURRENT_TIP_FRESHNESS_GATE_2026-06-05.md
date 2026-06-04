# AutoResearch: Current-Tip Freshness Gate

## Objective

Prevent stale launch evidence from satisfying the AutoResearch completion audit
after the remote branch advances.

## Sources Checked

- Git `merge-base --is-ancestor` documentation:
  `https://git-scm.com/docs/git-merge-base`
- GitHub push documentation on behind/non-fast-forward branches:
  `https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository`

## A/B Contract

- Baseline: `autoresearch_completion_audit.py` validated evidence paths and
  required text, but it could not tell whether the all-scope proof was stale
  after the branch moved.
- Variant: add optional `git_freshness` evidence validation. The audit now
  checks that a proof commit is an ancestor of the active remote ref and that
  every path changed after the proof commit is explicitly allowed as evidence
  or audit-infrastructure churn.
- Primary KPI: the default completion audit reports `15` criteria,
  `cycle_evidence_ready=true`, and `global_objective_complete=false` while the
  current proof remains fresh.
- Guardrail: a product-code path changed after the proof commit must make the
  contract invalid until a new all-scope proof is recorded.
- Decision rule: adopt only if focused tests cover the pass and fail paths, the
  default contract remains valid, and the pre-push-equivalent suite still
  passes.

## Adopted Variant

Adopted. The completion contract now includes required
`current_tip_freshness_gate` evidence. The configured launch proof commit is
`39d6a82`, and the active remote ref is
`origin/feat/observability-gateway-2026-05`.

Allowed changes after the proof commit are limited to:

- `docs/reports/2026-06/`
- `next-actions.md`
- `ops/references/autoresearch_completion_contract.json`
- `ops/scripts/autoresearch_completion_audit.py`
- `tests/test_autoresearch_completion_audit.py`

## Runtime Evidence

- `git merge-base --is-ancestor 39d6a82 origin/feat/observability-gateway-2026-05`
  - `ancestor=true`
- `git diff --name-only 39d6a82..origin/feat/observability-gateway-2026-05`
  - only report, next-actions, and completion-contract files were present
    before this slice
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-tip-freshness-2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_TIP_FRESHNESS_2026-06-05.md`
  - `15` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Verification

- `python -m pytest tests\test_autoresearch_completion_audit.py -q`
  - `6 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_autoresearch_completion_audit.py tests/test_mcp_service_runtime_smoke.py tests/test_mcp_otel_collector_handoff.py tests/test_agent_workflow_gate_runner.py tests/test_dev_server_browser_smoke.py tests/test_dev_server_mcp_contract.py tests/test_dev_server_mcp_runtime.py tests/test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `74 passed`
- Hook runtime probes:
  - dev-server MCP runtime smoke: `5` requests, `5` tools
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - single workflow dry-run selected `1`
  - side-effect safety execute selected `1` and skipped `1`
  - matrix dry-run covered `6` workflows and `6` selected gates
- `python -m py_compile ops\scripts\autoresearch_completion_audit.py`
  - passed
- Negative test coverage:
  - non-evidence paths such as `apps/product/app.py` after the proof commit
    invalidate the contract
  - a proof commit that is not an ancestor of the remote ref invalidates the
    contract

## Decision

This guard is adopted as release-evidence infrastructure. It does not mark the
global objective complete; it makes the open-ended loop safer by forcing a new
all-scope proof whenever product code changes after the current proof commit.
