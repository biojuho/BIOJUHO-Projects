# PR Analysis Read-Only Split

Generated at: `2026-06-05T11:42:00+09:00`

## Source Signal

- Repository: `google/adk-python`
- Commit: `10e5f07`
- Subject: `refactor: Separate PR analysis from triage for automation`
- Source URL: https://github.com/google/adk-python/commit/10e5f07
- Local interpretation: PR analysis should be runnable as a read-only automation lane, while triage/comment mutation remains a separate write-capable lane.

## A/B Contract

- Variant A: Keep one PR triage workflow that both analyzes pull-request metadata and writes a sticky PR comment.
- Variant B: Keep the existing triage workflow as-is, and add a separate read-only analysis mode/workflow that emits analysis artifacts without comment mutation.
- Adopted: Variant B.
- Decision rule: adopt only if the default triage output remains backward-compatible, the analysis workflow has no `issues: write` or `github-script` comment step, and both paths are covered by deterministic tests.

## Local Changes

- `.github/workflows/pr-analysis.yml`
  - Runs on pull requests with `contents: read` and `pull-requests: read`.
  - Calls `ops/scripts/pr_triage.py --mode analysis`.
  - Uploads only the `var/pr-analysis` artifact and appends a step summary.
- `ops/scripts/pr_triage.py`
  - Adds `--mode triage|analysis|both`, defaulting to `triage`.
  - Adds separate `pr-analysis.json` and `pr-analysis-summary.md` artifacts.
  - Keeps the existing `pr-triage.json`, `pr-triage-summary.md`, and `pr-triage-comment.md` defaults.
- `docs/PR_TRIAGE_SYSTEM.md`
  - Documents the read-only analysis workflow and local CLI mode.

## Verification

- `python -m pytest tests\test_pr_triage.py tests\test_github_workflows.py -q`
  - `14 passed`
- `python -m py_compile ops\scripts\pr_triage.py`
  - passed
- `python ops\scripts\pr_triage.py --base 8b1a920 --head 4439a39 --title "chore(mcp): add in-process dev-server smoke" --mode analysis --output-dir docs\reports\2026-06\PR_ANALYSIS_READ_ONLY_2026-06-05`
  - emitted `PR Analysis Snapshot`
  - emitted `No PR comment or mutation is required`
  - wrote `pr-analysis.json`
  - wrote `pr-analysis-summary.md`
- `global_objective_complete=false`
