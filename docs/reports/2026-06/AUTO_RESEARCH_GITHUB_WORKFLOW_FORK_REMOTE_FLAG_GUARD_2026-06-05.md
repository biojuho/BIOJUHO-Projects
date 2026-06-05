# AutoResearch GitHub Workflow Fork Remote Flag Guard - 2026-06-05

## Source Signal

- Source: `google/adk-python`
- Commit: `e87558cb0e39e7594b4dc9fa65ecb72c47f33957`
- URL: https://github.com/google/adk-python/commit/e87558cb0e39e7594b4dc9fa65ecb72c47f33957
- Signal: `ci: Remove unsupported --remote flag from gh repo fork`
- Upstream delta: replaced `gh repo fork google/adk-python --clone=false --remote=false || true` with `gh repo fork google/adk-python --clone=false || true`.

## A/B Contract

- Baseline: local workflow tests covered read-only PR analysis, dashboard release refresh, and workspace-smoke CI wiring, but did not guard against unsupported `gh repo fork ... --remote` usage.
- Variant: scan all `.github/workflows/*.yml` files and fail when a workflow line combines `gh repo fork` with `--remote`.
- Decision: adopted.

## Local Changes

- `tests/test_github_workflows.py`
  - Added `WORKFLOW_DIR`.
  - Added `test_github_workflows_avoid_unsupported_repo_fork_remote_flag`.
  - Reports exact workflow path and line number if the unsupported command shape returns.

## Verification

- `python -m pytest tests\test_github_workflows.py -q`
  - `7 passed`
- `python -m pytest tests\test_github_workflows.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q`
  - `26 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-github-workflow-fork-remote-flag-guard-2026-06-05.json`
  - `6/6 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - `83` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - `7` requirements
  - `global_objective_complete=false`
- `git diff --check`
  - passed with line-ending warnings only

## Completion State

- This is a source-backed workflow regression guard.
- It does not close the open-ended objective or external credential/runtime blockers.
- `global_objective_complete=false`
