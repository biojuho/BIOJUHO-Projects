# AutoResearch Completion Audit Push Gate - 2026-06-04

## Goal

Make the executable completion audit verify the repo-owned pre-push gate after the dev-server MCP runtime was added to that gate.

## Baseline

- The completion contract validated launch smoke, GitHub research, browser-click QA, remaining gaps, credential boundaries, and general commit/push evidence.
- It did not explicitly validate that the local pre-push hook protects the new MCP runtime tests.

## Variant

- Added required criterion `pre_push_regression_gate` to `ops/references/autoresearch_completion_contract.json`.
- The criterion validates:
  - `ops/hooks/pre-push` includes workspace smoke plus dev-server MCP contract/runtime tests.
  - `ops/hooks/pre-push` includes `ops/scripts/dev_server_mcp_runtime_smoke.py`.
  - `docs/reports/2026-06/AUTO_RESEARCH_PRE_PUSH_GATE_MCP_RUNTIME_2026-06-04.md` records `git push --dry-run`, `38 passed`, the subprocess smoke result, and the installed common hook path.
- Updated `tests/test_autoresearch_completion_audit.py` so the default contract must include this criterion.

## Verification

- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid
  - `8` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`
- `python -m pytest tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `4 passed`
- `python -m py_compile ops\scripts\autoresearch_completion_audit.py`
  - passed

## Decision

Accepted. The audit now fails if the pre-push gate drops MCP runtime coverage, drops subprocess smoke coverage, or loses its recorded dry-run evidence.
