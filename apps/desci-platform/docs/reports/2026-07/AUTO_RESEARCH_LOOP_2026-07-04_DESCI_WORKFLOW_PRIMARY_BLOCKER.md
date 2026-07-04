# AutoResearch Loop - DeSci Workflow Primary Blocker - 2026-07-04

## Objective

Add stable primary-blocker fields to provider apply workflow verification so downstream CI jobs can route on one blocker without parsing Markdown or scanning the full next-action list.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_WORKFLOW_PRIMARY_BLOCKER.md`

## Source Evidence

- Railway provider application still requires authenticated and linked CLI context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Vercel provider application still requires authenticated and linked CLI context.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local workflow evidence now has structured `next_required_actions`; downstream consumers still benefit from first-class primary routing fields.

## Baseline

- `next_required_actions` listed every required action in order.
- GitHub outputs exposed the action list as text and JSON.
- A downstream job still had to parse the list to identify the primary blocker.

## A/B Decision

- Baseline A: require downstream scripts to parse `next_required_actions_json`.
  - Rejected because every consumer would duplicate the same first-action extraction logic.
- Variant B: expose `primary_blocker`, `primary_blocker_scope`, `primary_blocker_reason`, and `primary_blocker_action` directly.
  - Adopted because it keeps the full list available while adding stable routing keys.

## Implementation

- Added primary-blocker extraction from the first structured `next_required_actions` item.
- Added provider apply workflow JSON fields:
  - `primary_blocker`
  - `primary_blocker_scope`
  - `primary_blocker_reason`
  - `primary_blocker_action`
- Added Markdown status rows and a `Primary Blocker` section.
- Added GitHub outputs:
  - `provider_apply_workflow_primary_blocker_scope`
  - `provider_apply_workflow_primary_blocker_reason`
  - `provider_apply_workflow_primary_blocker_action`
  - `provider_apply_workflow_primary_blocker_json`
- Added console summary output for `primary_blocker=scope/reason`.
- Updated success and blocked workflow tests.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `55 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `110 passed`
- `$env:GITHUB_OUTPUT='var\provider-apply-workflow-primary-blocker-github-output-2026-07-04.txt'; python scripts\external_gate_handoff.py --verify-provider-apply-workflow var\provider-apply-plan-context-2026-07-04.json --provider-apply-results var\provider-apply-results-context-blockers-2026-07-04.json --promotion-receipt var\post-apply-promotion-receipt-project-context-chain-2026-07-04.json --require-promotion-go --json-out var\provider-apply-workflow-primary-blocker-2026-07-04.json --markdown-out var\provider-apply-workflow-primary-blocker-2026-07-04.md --github-output`
  - Expected exit: `1`
  - Result: `provider_apply_workflow_ok=False`, provider preflight blockers `4`, project context missing `3`, failures `7`, next required actions `4`, `primary_blocker=provider_apply_plan/fill_provider_templates`, promotion blocking reasons `17`.
- `var\provider-apply-workflow-primary-blocker-2026-07-04.json`
  - `primary_blocker_scope=provider_apply_plan`
  - `primary_blocker_reason=fill_provider_templates`
  - `primary_blocker_action=Fill blank provider templates in a private local directory, then regenerate this apply plan with --preserve-provider-templates.`
- `var\provider-apply-workflow-primary-blocker-github-output-2026-07-04.txt`
  - Contains `provider_apply_workflow_primary_blocker_scope=provider_apply_plan`
  - Contains `provider_apply_workflow_primary_blocker_reason=fill_provider_templates`
  - Contains `provider_apply_workflow_primary_blocker_json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-workflow-primary-blocker-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The workflow output now has both full next-action detail and a stable primary blocker for downstream automation.

## Next Cycle

Continue hardening the workflow automation surface by validating generated GitHub-output values against the workflow JSON before CI consumers use them.
