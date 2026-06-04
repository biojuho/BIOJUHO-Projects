# AutoResearch Objective Text Quality Guard - 2026-06-05

## Objective

Make the prompt-to-artifact coverage manifest complete and auditable in the
same Korean language as the user's launch request.

## A/B Contract

- Baseline: `ops/references/autoresearch_objective_requirements.json` was valid
  JSON and passed objective coverage, but `objective_original` omitted the
  explicit `오토리서치 카파시 개념 스킬로 만들어줘` clause. Shell rendering also made
  prompt-text mojibake hard to spot reliably.
- Variant: restore the missing Korean objective clause and add a mojibake
  marker gate to `ops/scripts/autoresearch_objective_coverage.py`.
- Primary KPI: objective coverage remains valid while rejecting mojibake prompt
  terms in a deterministic regression test.
- Guardrails: completion audit, objective coverage, script compile, and focused
  objective/completion tests must pass.
- Decision: adopted. The manifest now preserves the original AutoResearch skill
  request, and the validator prevents prompt-text mojibake from passing as
  coverage evidence.

## Changed Paths

- `ops/references/autoresearch_objective_requirements.json`
- `ops/scripts/autoresearch_objective_coverage.py`
- `tests/test_autoresearch_objective_coverage.py`
- `ops/references/autoresearch_completion_contract.json`
- `docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json`
- `docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_TEXT_QUALITY_2026-06-05.json`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_TEXT_QUALITY_2026-06-05.md`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`

## Verification

- `python -m json.tool ops\references\autoresearch_objective_requirements.json`
  - passed
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid
  - `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`
- `python -m pytest tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `17` passed
- `git -c core.hooksPath=ops/hooks push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - hook passed through `116` pytest tests and runtime probes
  - dry-run push completed successfully after rebasing over the remote
    credential live-execution and hook check-mode slices
- `python -m py_compile ops\scripts\autoresearch_objective_coverage.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_TEXT_QUALITY_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_TEXT_QUALITY_2026-06-05.md`
  - valid
  - `25` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Next Cycle

Continue improving launch evidence without claiming global completion. The
remaining external credential/runtime boundary is still operator-owned.
