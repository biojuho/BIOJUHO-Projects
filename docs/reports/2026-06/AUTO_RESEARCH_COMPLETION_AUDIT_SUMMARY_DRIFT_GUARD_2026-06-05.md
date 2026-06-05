# AutoResearch: Completion Audit Summary Drift Guard

## Objective

Prevent checked-in completion audit summary artifacts from silently drifting
away from the current AutoResearch completion contract and Markdown renderer.

## A/B Contract

- Baseline: `autoresearch_completion_audit.py` could regenerate
  `AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json/.md`, but the test
  suite did not fail when the checked-in summary artifacts were stale.
- Variant: add a deterministic test that recomputes the completion summary from
  `ops/references/autoresearch_completion_contract.json` and compares both the
  JSON and Markdown artifacts byte-for-byte against the checked-in reports.
- Decision: adopted. This strengthens launch evidence by making the completion
  summary itself a checked artifact, not a manually refreshed proxy signal.

## Evidence

- `tests/test_autoresearch_completion_audit.py`
  - Added `test_checked_in_summary_artifacts_match_current_contract`.
  - Compares `AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json` against
    `json.dumps(summary, indent=2, ensure_ascii=False)`.
  - Compares `AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md` against
    `audit.format_markdown(summary)`.
- `ops/references/autoresearch_completion_contract.json`
  - Registers `completion_audit_summary_drift_guard` as covered evidence.
- `ops/references/autoresearch_objective_requirements.json`
  - Maps the guard into the quality-hardening requirement.

## Verification

- `python ops/scripts/autoresearch_completion_audit.py --json-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid `70` criteria
  - `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py --json-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `7` requirements
  - `global_objective_complete=false`
- `python -m pytest tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `18 passed`
- `python -m pytest tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py tests/test_pre_push_hook.py -q`
  - `24 passed`
- `python -m pytest tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py tests/test_pre_push_hook.py tests/test_external_credential_live_verify.py -q`
  - `34 passed` after ready-only evidence drift guard integration
- `python -m py_compile ops/scripts/autoresearch_completion_audit.py ops/scripts/autoresearch_objective_coverage.py`
  - passed

## Remaining Boundary

This guard does not make the open-ended objective globally complete. Continuous
A/B improvement and credential-gated external actions remain explicit blockers
until the user stops the loop or supplies the required operator credentials.
