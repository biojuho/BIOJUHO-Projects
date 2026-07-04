# AutoResearch Loop - DeSci Workflow Next Actions - 2026-07-04

## Objective

Add machine-readable next required actions to provider apply workflow verification so CI summaries and downstream release automation do not need to infer actions from free-form failures.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_WORKFLOW_NEXT_ACTIONS.md`

## Source Evidence

- Railway provider application remains blocked until CLI authentication and project-link context are resolved.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Vercel provider application remains blocked until CLI authentication and project-link context are resolved.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local no-go workflow evidence before this cycle exposed counts and failures but required downstream readers to infer action order from text.

## Baseline

- Provider apply workflow JSON exposed blocker counts and failure strings.
- Markdown listed plan blockers and promotion blockers.
- GitHub outputs exposed counts and blocked-reason text.
- No structured `next_required_actions` list existed for automation or CI summaries.

## A/B Decision

- Baseline A: keep only free-form failures and blocked-reason text.
  - Rejected because release automation would need to parse prose to determine the next operator action.
- Variant B: add structured action objects with `scope`, `reason`, `action`, and relevant counts.
  - Adopted because it preserves existing workflow semantics while making action routing deterministic.

## Implementation

- Added `_provider_apply_workflow_next_required_actions()` to derive action items from the apply plan, plan context, results verification, and promotion receipt verification.
- Added `next_required_actions` to provider apply workflow JSON.
- Added `summary.next_required_action_count`.
- Added a Markdown `Next Required Actions` section with scoped action rows and counts.
- Added GitHub outputs:
  - `provider_apply_workflow_next_required_action_count`
  - `provider_apply_workflow_next_required_actions`
  - `provider_apply_workflow_next_required_actions_json`
- Added console output for each `next_required_action`.
- Updated tests for success and blocked workflows.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `55 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `110 passed`
- `$env:GITHUB_OUTPUT='var\provider-apply-workflow-next-actions-github-output-2026-07-04.txt'; python scripts\external_gate_handoff.py --verify-provider-apply-workflow var\provider-apply-plan-context-2026-07-04.json --provider-apply-results var\provider-apply-results-context-blockers-2026-07-04.json --promotion-receipt var\post-apply-promotion-receipt-project-context-chain-2026-07-04.json --require-promotion-go --json-out var\provider-apply-workflow-next-actions-2026-07-04.json --markdown-out var\provider-apply-workflow-next-actions-2026-07-04.md --github-output`
  - Expected exit: `1`
  - Result: `provider_apply_workflow_ok=False`, provider preflight blockers `4`, project context missing `3`, failures `7`, next required actions `4`, promotion blocking reasons `17`.
- `var\provider-apply-workflow-next-actions-2026-07-04.json`
  - `summary.next_required_action_count=4`
  - Actions:
    - `provider_apply_plan/fill_provider_templates`, blocked providers `4`
    - `provider_preflight/provider_context_blocked`, provider preflight blockers `4`, project context missing `3`
    - `provider_apply_results/results_not_successful`, command failures `22`
    - `post_apply_promotion/promotion_receipt_not_go`, promotion blocking reasons `17`
- `var\provider-apply-workflow-next-actions-github-output-2026-07-04.txt`
  - Contains `provider_apply_workflow_next_required_action_count=4`
  - Contains multiline `provider_apply_workflow_next_required_actions`
  - Contains JSON `provider_apply_workflow_next_required_actions_json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-workflow-next-actions-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The workflow verifier now tells CI and operators exactly which action bucket must be handled next, while preserving the release no-go.

## Next Cycle

Continue hardening release automation by ensuring the workflow next-action JSON can be consumed safely by downstream scripts without relying on the Markdown report.
