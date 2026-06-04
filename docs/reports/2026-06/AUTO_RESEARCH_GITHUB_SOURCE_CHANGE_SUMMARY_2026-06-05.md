# AutoResearch: GitHub Source Change Summary

## Objective

Keep the continuous GitHub research loop actionable by comparing the newest
live repository metadata against the last adopted freshness snapshot.

## A/B Contract

- Baseline: the source freshness gate proved the tracked repositories were
  live and viable, but it did not identify which upstream projects moved since
  the adopted snapshot.
- Variant: add an explicit `--previous-json` comparison mode to
  `github_source_freshness.py` that reports changed, new, and removed tracked
  repositories without changing the default deterministic smoke path.
- Decision: adopted. The comparison turns external-source refreshes into a
  ranked follow-up signal while preserving the existing pass/fail viability
  gate and rate-limit boundary.

## Evidence

- `ops/scripts/github_source_freshness.py`
  - Adds `CHANGE_TRACKED_FIELDS`, `summarize_source_changes`, and
    `--previous-json`.
  - Tracks default branch, push/update timestamps, archive/disabled status,
    visibility, stars, forks, open issues, and license metadata.
- `docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json`
  - Live GitHub API result: `status=pass`, `source_count=30`, `failed=0`.
  - Compared against baseline
    `2026-06-04T18:54:22.968302+00:00`.
  - Result: `changed_repositories=27`, `new_repositories=0`,
    `removed_repositories=0`, so the current tracked set remains stable while
    27/30 upstream projects have metadata movement to review.
- `docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.md`
  - Renders the change summary and per-repository changed fields for operator
    review.

## Verification

- `python -m pytest tests/test_github_source_freshness.py -q`
  - `10 passed`
- `python -m pytest tests/test_github_source_freshness.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py tests/test_pre_push_hook.py -q`
  - `35 passed` after rebasing over dashboard pre-push stage markers
- `python ops/scripts/github_source_freshness.py --previous-json docs/reports/2026-06/GITHUB_SOURCE_FRESHNESS_2026-06-05.json --json-out docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json --markdown-out docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.md`
  - `30` sources, `passed=30`, `failed=0`
- `python ops/scripts/autoresearch_completion_audit.py`
  - valid `39` criteria, `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py`
  - valid `7` requirements, `global_objective_complete=false`

## Remaining Boundary

This is a source-movement detector, not a claim that every upstream change has
already been adopted locally. The global objective remains open:
`global_objective_complete=false`.
