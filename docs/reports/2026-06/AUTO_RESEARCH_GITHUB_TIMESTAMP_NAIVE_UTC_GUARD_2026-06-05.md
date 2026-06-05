# GitHub Timestamp Naive UTC Guard

- Date: 2026-06-05
- Source: `OpenHands/OpenHands`
- Source commit: `f2f77a666c9286a9df5b5a7d9597eca1e1ddc2c3`
- Source link: https://github.com/OpenHands/OpenHands/commit/f2f77a666c9286a9df5b5a7d9597eca1e1ddc2c3
- Source signal: `PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError)`
- Adopted local guard: naive-UTC GitHub timestamp parsing for commit-digest Atom windows
- global_objective_complete=false

## A/B Contract

Baseline: `github_source_commit_digest.py` parsed GitHub timestamps directly with `datetime.fromisoformat(...)`. That works for normal `Z` values, but a future source-change artifact with a naive window timestamp could be compared against an offset-aware Atom feed timestamp and raise a Python datetime comparison error.

Variant: `_github_ts_to_naive_utc()` now normalizes GitHub ISO timestamps to naive UTC before digest window comparisons. `Z` and non-UTC offsets are converted to the same naive UTC value, and already-naive timestamps are treated as UTC.

Adoption decision: adopted. The change keeps checked-in digest rendering stable while making the source-refresh path resilient to mixed timestamp forms.

## Evidence

- Script: `ops/scripts/github_source_commit_digest.py`
- Tests: `tests/test_github_source_commit_digest.py`

## Verification

- `python -m py_compile ops\scripts\github_source_commit_digest.py`
- `python -m pytest tests\test_github_source_commit_digest.py -q --tb=line` -> `9 passed`
