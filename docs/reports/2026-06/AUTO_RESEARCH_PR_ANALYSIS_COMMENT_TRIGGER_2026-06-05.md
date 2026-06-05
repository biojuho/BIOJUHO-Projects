# AutoResearch: PR Analysis Comment Trigger Guard

## Objective

Make the read-only PR analysis lane rerunnable from pull request comments while
preserving the artifact-only, no-comment-mutation boundary.

## Source Signal

- Source: `google/adk-python`
- Commit: `04924bfb446ac6c25a3bf5ae3acad0eea72afb90`
- URL: `https://github.com/google/adk-python/commit/04924bfb446ac6c25a3bf5ae3acad0eea72afb90`
- Relevant signal: CI analysis can be triggered from pull request comments.

## A/B Contract

- Baseline: `.github/workflows/pr-analysis.yml` only ran on `pull_request`
  events, so a reviewer could not rerun the read-only analysis after updates or
  after a missed transient run without pushing another commit.
- Variant: add a `/pr-analysis` `issue_comment` trigger that runs only when the
  comment belongs to a PR, resolves PR metadata with `gh api`, fetches the PR
  head ref, and writes the same `var/pr-analysis` artifact.
- Primary KPI: reviewers can rerun artifact-only PR analysis from pull request
  comments without granting comment write permissions.
- Guardrails: keep `contents: read`, `pull-requests: read`, and `issues: read`;
  keep `issues: write` absent; keep `github-script` absent; keep PR issue
  comments ignored when they are not attached to a PR.
- Decision: adopted.

## Implementation

- `.github/workflows/pr-analysis.yml`
  - Adds `issue_comment` `created` trigger.
  - Gates execution to PR comments containing `/pr-analysis`.
  - Resolves PR context into `var/pr-analysis/pr-context.json`,
    `pr-title.txt`, and `pr-body.md`.
  - Fetches the base branch and `refs/pull/${PR_NUMBER}/head`, then passes the
    resolved PR head ref and body file to `ops/scripts/pr_triage.py`.
- `tests/test_github_workflows.py`
  - Locks the comment trigger, PR-only guard, read-only permissions, and absence
    of write/comment mutation helpers.
- `docs/PR_TRIAGE_SYSTEM.md`
  - Documents the `/pr-analysis` manual rerun path and artifact-only analysis
    contract.

## Verification

- `python -m pytest tests\test_github_workflows.py -q`
  - `4 passed`
- `python -m pytest tests\test_github_workflows.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_github_source_commit_digest.py -q`
  - `59 passed`
- YAML parse check for `.github/workflows/pr-analysis.yml`
  - `workflow yaml ok`
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-pr-analysis-comment-trigger-completion.json --markdown-out var\autoresearch-pr-analysis-comment-trigger-completion.md`
  - valid `70` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-pr-analysis-comment-trigger-objective.json --markdown-out var\autoresearch-pr-analysis-comment-trigger-objective.md`
  - valid `7` requirements
  - `global_objective_complete=false`
- `git diff --check`
  - passed
- `python ops\hooks\install_hooks.py --check`
  - hook current

## Remaining Boundary

This cycle improves the GitHub PR analysis operator loop, but the global
AutoResearch objective remains open-ended until the user explicitly stops it.

global_objective_complete=false
