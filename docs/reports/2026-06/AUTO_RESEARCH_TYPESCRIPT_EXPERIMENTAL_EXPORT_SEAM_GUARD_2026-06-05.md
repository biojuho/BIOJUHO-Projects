# AutoResearch TypeScript Experimental Export Seam Guard

- Date: `2026-06-05`
- Source: `vercel/ai@beb6c72357fc970c3985a9b7e5ec346622102f28`
- Source URL: `https://github.com/vercel/ai/commit/beb6c72357fc970c3985a9b7e5ec346622102f28`
- Source signal: `docs(contributing): document the Experimental_ prefix seam convention (#15833)`
- Local scope: `CONTRIBUTING.md`, `ops/scripts/typescript_export_convention_audit.py`, `tests/test_typescript_export_convention_audit.py`
- global_objective_complete=false

## Source-backed hypothesis

Vercel documented a seam-only convention for experimental API prefixes: implementation declarations stay unprefixed, while `Experimental_*` and `experimental_*` are applied only where symbols cross package import/export seams. The local workspace has several TypeScript and JavaScript public surfaces but no deterministic guard for accidental experimental-prefix leakage.

## A/B decision

- Baseline: contributor guidance had no experimental TypeScript export rule, and no audit could detect a prefixed declaration or unaliased prefixed import.
- Variant: add workspace guidance plus an executable audit that scans active TS/JS source roots and fails on prefixed declarations, direct prefixed exports, and prefixed imports that are not aliased to plain local names.
- Primary KPI: audit detects convention violations while the current workspace reports `0 violations`.
- Guardrail: no runtime code or public API behavior changes.
- Decision: accepted. This is a low-risk launch-readiness guard for future experimental API work.

## Evidence

- `python -m pytest tests\test_typescript_export_convention_audit.py -q --tb=line` -> `5 passed`
- `python -m py_compile ops\scripts\typescript_export_convention_audit.py` -> passed
- `python ops\scripts\typescript_export_convention_audit.py --json-out docs\reports\2026-06\TYPESCRIPT_EXPORT_CONVENTION_AUDIT_2026-06-05.json --markdown-out docs\reports\2026-06\TYPESCRIPT_EXPORT_CONVENTION_AUDIT_2026-06-05.md` -> `pass`, `164 files`, `0 violations`, `0 accepted aliases`

## Follow-up

Add this audit to a narrower CI/pre-push lane only after the next batch proves it stays fast across source-root growth.
