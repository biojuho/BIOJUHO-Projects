# GitHub Modernization Radar Drift Guard

## Decision

Add a deterministic guard for the checked-in GitHub modernization radar report.
The live source freshness snapshot already proves repository metadata recency; this guard separately proves that `docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md` still matches the current `ops/references/github_modernization_sources.json` manifest and `ops/scripts/github_modernization_radar.py` Markdown renderer.

## Adopted Variant

- `tests/test_github_modernization_radar.py` now includes `test_checked_in_modernization_report_matches_manifest_renderer`.
- The test loads `REPORT_MARKDOWN_PATH`, validates the manifest against real workspace evidence, recomputes `format_markdown(payload, summary)`, and compares the checked-in Markdown exactly.
- The check is offline and does not call the GitHub API.

## Verification

- `python -m pytest tests/test_github_modernization_radar.py -q` -> `5 passed`.
- `python ops\scripts\autoresearch_completion_audit.py` -> completion audit remains valid with `global_objective_complete=false`.
- `python ops\scripts\autoresearch_objective_coverage.py` -> objective coverage remains valid with `global_objective_complete=false`.

## Remaining Boundary

This guard prevents stale source-mapping reports from satisfying the AutoResearch GitHub evidence contract. It does not replace live GitHub source freshness refreshes; those still require available GitHub API quota or `GITHUB_TOKEN` / `GH_TOKEN` when unauthenticated quota is exhausted.
