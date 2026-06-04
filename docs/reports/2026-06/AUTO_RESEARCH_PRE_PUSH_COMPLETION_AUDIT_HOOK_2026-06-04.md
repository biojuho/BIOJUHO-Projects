# AutoResearch Pre-Push Completion Audit Hook - 2026-06-04

## Objective

Make the real Git pre-push gate execute the AutoResearch completion audit, so a
broken objective-to-artifact contract blocks pushes before the branch moves.

## A/B Contract

- Baseline: the hook ran workspace/MCP runtime tests and the MCP subprocess
  smoke, but the executable completion audit was not part of the push gate.
- Variant: add `tests/test_autoresearch_completion_audit.py` to the pytest
  smoke list and run `python ops/scripts/autoresearch_completion_audit.py` after
  the MCP subprocess smoke.
- Primary KPI: a real `git push --dry-run` invokes the installed hook and passes
  pytest, MCP subprocess smoke, and completion audit.
- Guardrail: the completion audit must still report
  `global_objective_complete=false`.

## Verification

- `python -m pytest tests\test_pre_push_hook.py tests\test_autoresearch_completion_audit.py tests\test_dev_server_mcp_runtime_smoke.py`
  - Result: `7 passed`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-pre-push-hook-2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_PRE_PUSH_HOOK_2026-06-04.md`
  - Result: valid, `9` criteria, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.
- `python ops\hooks\install_hooks.py`
  - Result: installed `pre-push` to `D:\AI project\.git\hooks\pre-push`.
- `git push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - Result: hook passed `42` tests, MCP subprocess smoke, and completion audit;
    Git reported `Everything up-to-date`.

## Decision

Adopted. Future pushes on this checkout now exercise both the executable MCP
runtime smoke and the executable AutoResearch completion audit before updating
the remote branch.
