# AutoResearch: GitHub Source Snapshot Manifest Drift Guard

## Objective

Prevent the checked-in GitHub source freshness snapshot from drifting away from
the current modernization source manifest without requiring another live GitHub
API refresh.

## A/B Contract

- Baseline: the completion contract required a passing `30/30` source snapshot,
  but tests did not prove that the checked-in snapshot still matched every
  current manifest repo, category, adoption status, and viability rule.
- Variant: add an offline deterministic test that compares
  `GITHUB_SOURCE_FRESHNESS_2026-06-05.json` against
  `ops/references/github_modernization_sources.json`, validates the snapshot
  timestamp, checks all repo records in order, and verifies the Markdown report
  matches the current renderer.
- Decision: adopted. This keeps the last complete live snapshot usable as
  evidence while making manifest/snapshot drift visible before push.

## Evidence

- `tests/test_github_source_freshness.py`
  - Added `test_checked_in_source_snapshot_matches_manifest_and_renderer`.
  - Verifies `source_count=30`, `passed=30`, `failed=0`, and
    `manifest_generated_at` matches the manifest.
  - Verifies each snapshot record has the same repo, category, and adoption
    status as the manifest source at the same position.
  - Reuses `_metadata_viability_error` so archived, disabled, or incomplete
    metadata cannot remain accepted in the checked-in snapshot.
  - Compares checked-in Markdown against `render_markdown(snapshot)`.
- `docs/reports/2026-06/GITHUB_SOURCE_FRESHNESS_2026-06-05.md`
  - Updated from the current renderer to include `Complete`, `Partial`,
    `Rate-limited failures`, and `Token available`.

## Verification

- `python -m pytest tests/test_github_source_freshness.py -q`
  - `8 passed`
- `python -m pytest tests/test_github_source_freshness.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `27 passed`
- `python -m pytest tests/test_github_source_freshness.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py tests/test_pre_push_hook.py -q`
  - `33 passed`
- `python -m py_compile ops/scripts/github_source_freshness.py ops/scripts/autoresearch_completion_audit.py ops/scripts/autoresearch_objective_coverage.py`
  - passed
- `python ops/scripts/autoresearch_completion_audit.py`
  - valid `29` criteria after contract registration
  - `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py`
  - valid `7` requirements
  - `global_objective_complete=false`

## Remaining Boundary

This guard is an offline manifest/snapshot consistency proof. A new live
freshness snapshot still requires a successful `30/30` GitHub API run, and if
unauthenticated quota is exhausted the operator must provide `GITHUB_TOKEN` or
`GH_TOKEN`.
