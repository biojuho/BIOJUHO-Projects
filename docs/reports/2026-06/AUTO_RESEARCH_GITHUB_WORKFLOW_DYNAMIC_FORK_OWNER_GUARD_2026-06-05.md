# GitHub Workflow Dynamic Fork Owner Guard

- Date: 2026-06-05
- Source repo: `google/adk-python`
- Source commit: `faa5db63c5761d87093e27e1969a221ea3d4997a`
- Source signal: `ci: Dynamically resolve bot fork repo to prevent push failures`
- Source URL: https://github.com/google/adk-python/commit/faa5db63c5761d87093e27e1969a221ea3d4997a
- Local status: adopted
- Global objective complete: `false`

## Source Signal

ADK changed an issue-fix workflow to query the authenticated bot username with `gh api user --jq .login`, ensure the fork exists, push to `github.com/${BOT_USER}/adk-python.git`, and open the PR with `--head "${BOT_USER}:$BRANCH_NAME"` instead of hard-coding a bot fork owner.

## A/B Contract

- A: Keep workflow tests limited to the unsupported `gh repo fork --remote` shape and allow future automation to hard-code fork owners in push remotes or PR heads.
- B: Add a workflow regression test that rejects static fork push targets and static `--head owner:branch` values in `.github/workflows/*.yml`, while allowing dynamic owners such as `${BOT_USER}`.

Decision: adopted B. It is low-risk, covers a real CI push-failure class, and complements the existing unsupported `gh repo fork --remote` guard without changing production runtime behavior.

## Local Changes

- `tests/test_github_workflows.py`
  - Added `test_github_workflows_avoid_static_fork_owner_push_targets`.
  - Prevents hard-coded fork owners from entering workflow push and PR creation paths.
  - Scans workflow YAML for `git remote add fork` lines with hard-coded `github.com/owner/repo.git` targets.
  - Scans workflow YAML for static `--head owner:branch` PR creation targets.

## Verification

- `python -m pytest tests\test_github_workflows.py -q` -> `8 passed`
- `python -m pytest tests\test_github_workflows.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q` -> `27 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-github-workflow-dynamic-fork-owner-guard-2026-06-05.json` -> `6/6 passed`

## Completion State

- `global_objective_complete=false`
