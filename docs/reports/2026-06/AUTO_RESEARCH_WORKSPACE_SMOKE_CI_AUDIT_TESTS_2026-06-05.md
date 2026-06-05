# Workspace Smoke CI AutoResearch Audit Tests

Generated at: `2026-06-05T10:25:00+09:00`

## Source Signal

- Repository: `microsoft/agent-framework`
- Commit: `f3c3efed4301905cff795794790bd4b4719742a4`
- Subject: `Python: Add GitHub Copilot integration tests to CI workflows (#6346)`
- Source URL: https://github.com/microsoft/agent-framework/commit/f3c3efed4301905cff795794790bd4b4719742a4

The upstream change adds a dedicated provider integration-test job to CI and wires it into workflow reporting. The local adoption target is the same class of guard: AutoResearch audit regressions should run in GitHub Actions, not only in local pre-push hooks.

## A/B Contract

- Variant A: Keep AutoResearch audit drift tests local-only through the pre-push hook.
- Variant B: Add a branch-portable AutoResearch audit regression step to `.github/workflows/workspace-smoke.yml`.
- Adopted: Variant B.
- Reason: The CI workflow already installs the full workspace and runs smoke gates; adding branch-portable AutoResearch audit regression tests catches audit artifact drift on PR and push while leaving branch-bound freshness validation to pre-push and local audit runs.

## Local Changes

- `.github/workflows/workspace-smoke.yml` now runs `tests/test_github_workflows.py`, `tests/test_autoresearch_ci_regression.py`, and `tests/test_autoresearch_objective_coverage.py` after the full workspace smoke suite.
- `tests/test_github_workflows.py` locks the workflow step name, command, UTF-8 environment, and ordering before summary upload.
- `tests/test_autoresearch_ci_regression.py` audits the checked-in completion contract after removing volatile freshness keys: `git_freshness`, `protected_path_freshness`, and `json_freshness`.

## Verification

- `python -m pytest tests/test_github_workflows.py tests/test_autoresearch_ci_regression.py tests/test_autoresearch_objective_coverage.py -q`
  - `10 passed`
- `python -m pytest tests/test_github_workflows.py tests/test_autoresearch_ci_regression.py tests/test_autoresearch_objective_coverage.py tests/test_autoresearch_completion_audit.py automation/getdaytrends/tests/test_main.py packages/shared/harness/tests/test_token_tracker.py -q`
  - `65 passed`
  - Warning: existing `pytest.mark.flaky` marker is not registered in `automation/getdaytrends/tests/test_main.py`.
- `python ops/scripts/autoresearch_completion_audit.py --json-out var/autoresearch-workspace-smoke-ci-audit-completion.json --markdown-out var/autoresearch-workspace-smoke-ci-audit-completion.md`
  - valid `50` criteria
  - `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py --json-out var/autoresearch-workspace-smoke-ci-audit-objective.json --markdown-out var/autoresearch-workspace-smoke-ci-audit-objective.md`
  - valid `7` requirements
  - `global_objective_complete=false`
- `git diff --check`
  - passed
- `python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var/workspace-smoke-getdaytrends-ci-audit-baseline-2026-06-05.json`
  - passed `2/2`
- `python ops/hooks/install_hooks.py --check`
  - passed; installed pre-push hook is current

## Boundaries

- This CI guard does not replace `current_tip_freshness_gate` or `direct_browser_qa_freshness_gate`.
- Branch-bound git freshness remains in the local completion audit and pre-push path because GitHub Actions checkouts for `main` and `dev` may not fetch `origin/feat/observability-gateway-2026-05`.
- `global_objective_complete=false`.
