# AutoResearch Completion Audit Browser JSON Promotion - 2026-06-04

## Objective

Promote the new DeSci machine-readable browser smoke artifact into the
AutoResearch completion contract so app-click QA is not represented only by
human prose reports.

## A/B Contract

- Baseline: `direct_app_click_qa` cited dashboard, AgriGuard, and DeSci prose
  reports.
- Variant: keep the prose evidence, but add
  `docs/reports/2026-06/DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json` as
  required DeSci browser evidence.
- Primary KPI: completion audit remains valid and verifies JSON terms for
  `status=pass`, `passed=7`, `failed=0`, `planned=7`, and protected redirect
  route names.
- Guardrail: global objective must remain incomplete because the user requested
  an open-ended loop and Canva OAuth remains credential-bound.

## Verification

- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-after-browser-json-2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_AFTER_BROWSER_JSON_2026-06-04.md`
  - Result: valid, `9` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.
- `python -m pytest tests\test_autoresearch_completion_audit.py`
  - Result: `4 passed`.

## Decision

Adopted. The completion contract now checks the JSON browser artifact produced
by the previous DeSci smoke slice while preserving the open-ended global
completion policy.
