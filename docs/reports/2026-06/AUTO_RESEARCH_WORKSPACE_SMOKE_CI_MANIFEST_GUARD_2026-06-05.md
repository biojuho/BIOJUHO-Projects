# AutoResearch Workspace Smoke CI Manifest Guard - 2026-06-05

## Source Signal

- Source: `microsoft/agent-framework`
- Commit: `f3c3efed4301905cff795794790bd4b4719742a4`
- URL: https://github.com/microsoft/agent-framework/commit/f3c3efed4301905cff795794790bd4b4719742a4
- Signal: `Python: Add GitHub Copilot integration tests to CI workflows (#6346)`

## A/B Contract

- Baseline: workspace CI ran AutoResearch workflow/audit tests after the smoke suite, but the manifest validator tests were only covered by local/pre-push paths.
- Variant: add `tests/test_agent_workflow_manifest.py` to the workspace CI AutoResearch audit regression step and lock that workflow command with `tests/test_github_workflows.py`.
- Decision: adopted.

## Local Changes

- `.github/workflows/workspace-smoke.yml`
  - Runs `tests/test_agent_workflow_manifest.py` inside `Run AutoResearch audit regression tests`.
- `tests/test_github_workflows.py`
  - Asserts the CI workflow keeps `tests/test_agent_workflow_manifest.py` wired into the AutoResearch audit regression command.

## Verification

- `python -m pytest tests\test_github_workflows.py -q`
  - `6 passed`
- `python -m pytest tests\test_github_workflows.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q`
  - `25 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-ci-manifest-guard-2026-06-05.json`
  - `6/6 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - `82` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - `7` requirements
  - `global_objective_complete=false`
- `git diff --check`
  - passed with line-ending warnings only

## Completion State

- This hardens the CI path for the manifest role-policy guard.
- It does not close the open-ended objective or external credential/runtime blockers.
- `global_objective_complete=false`
