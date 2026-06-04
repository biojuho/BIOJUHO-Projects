# AutoResearch: GitHub Source Viability Gate

## Objective

Make the GitHub source freshness check fail when a tracked repository is no
longer a viable primary source, instead of only recording archived or disabled
state as passive metadata.

## A/B Contract

- Baseline: `github_source_freshness.py` records `archived`, `disabled`,
  `default_branch`, `pushed_at`, and `updated_at`, but any successful GitHub API
  response counts as a pass.
- Variant: fail the per-repo freshness record if metadata shows
  `archived=true`, `disabled=true`, or a missing core field such as
  `default_branch`, `pushed_at`, or `updated_at`.
- Primary KPI: non-viable source metadata is rejected by deterministic tests
  while the current 22-source snapshot remains viable.
- Guardrail: do not require a live GitHub rerun when the unauthenticated API is
  rate-limited; keep the rate-limit boundary visible and validate the last
  successful live snapshot offline.

## Result

Adopted.

- Focused source freshness tests: `5 passed`
- Focused source/radar/audit tests: `20 passed`
- Pre-push-equivalent pytest suite: `89 passed`
- Runtime probes passed:
  - dev-server MCP runtime smoke
  - MCP service runtime smoke
  - single workflow dry-run
  - side-effect safety skip
  - all-workflow matrix dry-run
- Completion audit: `21` criteria, `cycle_evidence_ready=true`,
  `global_objective_complete=false`

## Evidence

- `ops/scripts/github_source_freshness.py`
  - Added `_metadata_viability_error`.
  - Fails archived repositories.
  - Fails disabled repositories.
  - Fails missing `html_url`, `default_branch`, `pushed_at`, or `updated_at`.
  - Markdown output now includes a `Disabled` column.
- `tests/test_github_source_freshness.py`
  - Covers `repository is archived`, `repository is disabled`, and
    `missing default_branch`.
- Cached live snapshot viability:
  - Source: `docs/reports/2026-06/GITHUB_SOURCE_FRESHNESS_2026-06-05.json`
  - Snapshot status: `pass`
  - Source count: `22`
  - Passed: `22`
  - Failed: `0`
  - Offline viability check: `viability_errors=[]`
- Live rerun boundary:
  - A stricter live rerun attempted after the code change hit GitHub's
    unauthenticated API rate limit after 8 repositories.
  - `GITHUB_TOKEN` and `GH_TOKEN` were not available in the environment.
  - The failed partial rerun artifact was not adopted; the last successful
    22-source live snapshot was restored and validated offline.
