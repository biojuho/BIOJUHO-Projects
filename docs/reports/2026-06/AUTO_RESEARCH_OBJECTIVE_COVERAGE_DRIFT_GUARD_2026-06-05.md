# AutoResearch: Objective Coverage Drift Guard

## Objective

Prevent checked-in prompt-to-artifact objective coverage artifacts from silently
drifting away from the current requirements manifest or Markdown renderer.

## A/B Contract

- Baseline: `autoresearch_objective_coverage.py` could regenerate
  `AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json/.md`, but checked-in
  artifacts were not compared against the current requirements manifest in the
  test suite.
- Variant: add a deterministic test that recomputes objective coverage from
  `ops/references/autoresearch_objective_requirements.json`, validates the JSON
  artifact's `generated_at` timestamp, normalizes only that timestamp, and then
  compares both JSON and Markdown artifacts against the current renderer output.
- Decision: adopted. This closes the prompt-to-artifact side of the audit
  evidence chain without making the open-ended global objective complete.

## Evidence

- `tests/test_autoresearch_objective_coverage.py`
  - Added `test_checked_in_coverage_artifacts_match_current_requirements`.
  - Validates checked-in JSON `generated_at` as ISO-8601.
  - Compares every other JSON field against the current audit result.
  - Compares checked-in Markdown against `coverage.format_markdown(report)`.
- `ops/references/autoresearch_completion_contract.json`
  - Registers `objective_coverage_artifact_drift_guard` as covered evidence.
- `ops/references/autoresearch_objective_requirements.json`
  - Maps the guard into the quality-hardening requirement.

## Verification

- `python ops/scripts/autoresearch_completion_audit.py --json-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid `56` criteria
  - `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py --json-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `7` requirements
  - `global_objective_complete=false`
- `python -m pytest tests/test_autoresearch_objective_coverage.py tests/test_autoresearch_completion_audit.py -q`
  - `19 passed`
- `python -m pytest tests/test_autoresearch_objective_coverage.py tests/test_autoresearch_completion_audit.py tests/test_pre_push_hook.py -q`
  - `25 passed`
- `python -m py_compile ops/scripts/autoresearch_objective_coverage.py ops/scripts/autoresearch_completion_audit.py`
  - passed

## Remaining Boundary

This guard proves the checked-in objective coverage artifacts are current. It
does not remove the continuous GitHub research/A-B loop requirement or the
operator-owned external credential boundaries.
