# AutoResearch Agent Workflow Role Policy Guard - 2026-06-05

## Source Signal

- Source: `strands-agents/harness-sdk`
- Commit: `050ab14955a4ee0adf7b2b21df0124b6c094630a`
- URL: https://github.com/strands-agents/harness-sdk/commit/050ab14955a4ee0adf7b2b21df0124b6c094630a
- Signal: `fix: add maintain role to auto-strands-review allowed-roles (#2633)`
- Upstream delta: `allowed-roles: 'triage,write,maintain,admin'`

## A/B Contract

- Baseline: `ops/references/agent_workflows.json` declared per-workflow `agent_roles`, but `agent_workflow_manifest.py` only verified that each role was a non-empty string.
- Variant: add an explicit top-level `role_policy`, require every workflow role to appear in `role_policy.allowed_agent_roles`, and require `role_policy.review_allowed_roles` to include `maintain`.
- Decision: adopted.

## Local Changes

- `ops/references/agent_workflows.json`
  - Added `role_policy` with `15` allowed workflow roles.
  - Added review roles `triage`, `write`, `maintain`, and `admin`.
- `ops/scripts/agent_workflow_manifest.py`
  - Added `_validate_role_policy`.
  - Rejects undeclared workflow roles.
  - Rejects duplicate policy roles.
  - Rejects a review-role policy that omits `maintain`.
  - Renders role-policy metadata in JSON and Markdown summaries.
- `tests/test_agent_workflow_manifest.py`
  - Covers the current policy summary.
  - Covers unknown workflow roles, duplicate policy roles, and missing `maintain`.
- `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - Regenerated with the `Role Policy` section.

## Verification

- `python -m pytest tests\test_agent_workflow_manifest.py -q`
  - `10 passed`
- `python -m py_compile ops\scripts\agent_workflow_manifest.py`
  - passed
- `python ops\scripts\agent_workflow_manifest.py --json-out var\agent-workflow-manifest-role-policy-2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `6` workflows valid
  - launch statuses: `active=6`
  - allowed agent roles: `15`
  - review roles: `triage, write, maintain, admin`
- `python -m pytest tests\test_agent_workflow_manifest.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q`
  - `29 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-agent-workflow-role-policy-2026-06-05.json`
  - `6/6 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - `81` criteria
  - `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - `7` requirements
  - `global_objective_complete=false`
- `git diff --check`
  - passed with line-ending warnings only

## Completion State

- This is a source-backed adopted improvement inside the continuous loop.
- It does not close the open-ended objective or external credential/runtime blockers.
- `global_objective_complete=false`
