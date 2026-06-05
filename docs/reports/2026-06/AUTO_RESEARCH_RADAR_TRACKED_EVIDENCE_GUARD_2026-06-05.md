# AutoResearch Radar Tracked Evidence Guard - 2026-06-05

## Source Signal

- Upstream: `dsifry/metaswarm`
- URL: https://github.com/dsifry/metaswarm
- Pattern adopted: quality gates should validate independently, require file-backed evidence, and keep durable work records in version control.

## A/B Contract

- Baseline: `ops/scripts/github_modernization_radar.py` required local evidence paths to be repo-relative and present on disk, but it accepted local-only untracked files.
- Variant: require every `local_evidence` path to pass `git ls-files --error-unmatch`, then replace existing local-only evidence references with tracked equivalents.
- Primary KPI: prevent the modernization radar from citing artifacts that disappear after checkout, clone, or CI.
- Guardrails: preserve the existing schema, adoption counts, CLI output shape, and generated markdown structure.
- Decision: accepted. The radar now rejects untracked evidence while keeping the current source map valid.

## Changes

- `ops/scripts/github_modernization_radar.py`
  - Adds a git-tracking check after path existence validation.
  - Emits `must be tracked by git` for local-only evidence files.
- `tests/test_github_modernization_radar.py`
  - Adds a synthetic temp-workspace fixture proving untracked local evidence is rejected.
- `ops/references/github_modernization_sources.json`
  - Removes or replaces six local-only evidence references across five unique paths:
    - `ops/scripts/workspace_smoke_report.py`
    - `packages/shared/tests/test_workflow_trace.py`
    - `ops/scripts/release_approval_check.py`
    - `docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json`
    - `docs/MCP_HEALTH_CHECK.md`
  - Adds tracked radar validator/test evidence to the `dsifry/metaswarm` row.

## Verification

- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-tracked-evidence-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed.
  - Counts: `adopted=4`, `partially_adopted=1`, `watch=1`.
- `python -m pytest tests\test_github_modernization_radar.py -q`
  - Passed `5/5`.
- `python -m pytest tests\test_github_modernization_radar.py tests\test_workspace_smoke.py -q --tb=line -p no:cacheprovider`
  - Passed `33/33`.
- `python -m py_compile ops\scripts\github_modernization_radar.py`
  - Passed.

## Notes

- The generated radar JSON stays under `var/` and is not staged.
- This guard intentionally allows newly added report files only after they are staged or committed, matching the durability rule it enforces.
