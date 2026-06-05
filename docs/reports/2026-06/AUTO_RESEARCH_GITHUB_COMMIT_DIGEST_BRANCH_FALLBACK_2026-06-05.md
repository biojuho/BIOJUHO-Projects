# AutoResearch GitHub Commit Digest Branch Fallback

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Source signal: live GitHub digest retry found `Significant-Gravitas/AutoGPT`
  reachable while unauthenticated GitHub API commit requests were rate-limited
  and the `main.atom` fallback did not match the repository default branch.
- Source link: https://github.com/Significant-Gravitas/AutoGPT

## A/B Contract

- Baseline: `github_source_commit_digest.py` fell back from rate-limited GitHub
  API commit requests to `commits/main.atom` only. Repositories whose default
  branch is not `main`, such as AutoGPT on `master`, could mark the whole digest
  failed even though the repository remained live and viable.
- Variant: when the API is rate-limited, try `commits/main.atom`,
  `commits/master.atom`, and then the repository default `commits.atom` feed
  before marking the repository failed.
- Primary KPI: the top-12 live digest completes with `failed_repositories=0`.
- Guardrails: actual repository/feed failures still fail the selected item; the
  digest still reports empty commit windows as `no_local_adoption_commit_window_empty`.
- Decision rule: adopt only if the branch-fallback unit test passes, the script
  compiles, and the live top-12 digest passes with AutoGPT no longer blocked.

## Result

- Adopted variant: yes.
- Added `_commit_feed_urls()` with `main`, `master`, and default commits feed
  URLs.
- Added a regression for `main.atom` returning 404 and `master.atom` succeeding.
- Live top-12 digest passed with `selected=12`, `failed=0`.
- `Significant-Gravitas/AutoGPT` now reports
  `no_local_adoption_commit_window_empty` instead of
  `blocked_until_commit_digest_fetch_passes`.

## Changed Paths

- `ops/scripts/github_source_commit_digest.py`
- `tests/test_github_source_commit_digest.py`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_BRANCH_FALLBACK_2026-06-05.json`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_BRANCH_FALLBACK_2026-06-05.md`

## Verification

- `python -m pytest tests\test_github_source_commit_digest.py -q`
  - Passed: `7`.
- `python -m py_compile ops\scripts\github_source_commit_digest.py`
  - Passed.
- `python ops\scripts\github_source_commit_digest.py --top 12 --max-commits 8 --json-out docs\reports\2026-06\GITHUB_SOURCE_COMMIT_DIGEST_BRANCH_FALLBACK_2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SOURCE_COMMIT_DIGEST_BRANCH_FALLBACK_2026-06-05.md`
  - Passed: `selected=12`, `failed=0`.

## Next Cycle

- Continue selecting source-backed hardening targets from the now-complete
  digest; prefer changes that reduce launch risk without needing external
  credentials.

## Audit Marker

- `global_objective_complete=false`
