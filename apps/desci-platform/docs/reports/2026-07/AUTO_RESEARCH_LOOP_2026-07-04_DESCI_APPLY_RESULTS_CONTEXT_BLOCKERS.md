# AutoResearch Loop - DeSci Apply Results Context Blockers - 2026-07-04

## Objective

Carry provider CLI authentication and project-context blockers from the provider apply plan into apply-results receipts, apply-results verification, and final provider apply workflow verification.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_APPLY_RESULTS_CONTEXT_BLOCKERS.md`

## Source Evidence

- Railway provider application still depends on a CLI session linked to the intended project.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Vercel provider application still depends on authenticated CLI/project context.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local evidence from the prior cycle: `var\provider-apply-plan-context-2026-07-04.json` reports `ready_to_apply=false`, provider preflight blockers `4`, and project context missing `3`.

## Baseline

- Execute-mode apply-results recording blocked a not-ready plan, but each blocked command only reported `provider apply plan is not ready_to_apply`.
- Apply-results verification could evaluate command receipts without independently failing on plan readiness.
- Provider apply workflow verification did not expose provider preflight blocker counts or project-context blocker counts at the top level, in Markdown, or in GitHub outputs.

## A/B Decision

- Baseline A: rely on the nested apply-plan verifier to explain provider context blockers.
  - Rejected because operators reviewing apply-results receipts or workflow summaries could miss the provider auth/linking reason.
- Variant B: carry the plan execution context into results receipts, results verification, workflow verification, Markdown, annotations, and GitHub outputs.
  - Adopted because every workflow layer now fails closed with the same provider-context counts.

## Implementation

- Added `_provider_apply_plan_execution_context()` to summarize plan readiness, operator stage, blocked providers, provider preflight blocker count, project-context missing count, plan blocked reasons, and provider blocked reasons.
- Added plan-context fields to provider apply-results templates and recorded apply-results receipts.
- Changed execute-mode apply-results recording to block before invoking provider commands when the plan is not ready, with the full plan-context blocker reason.
- Changed apply-results verification to fail closed when the referenced plan is not ready, even if the receipt is success-shaped.
- Changed provider require-ready verification to use each provider's actual blocked reason instead of a hard-coded blank-template reason.
- Added provider preflight and project-context counts to provider apply workflow JSON, Markdown, console output, annotations, and GitHub outputs.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `55 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `110 passed`
- `python scripts\external_gate_handoff.py --record-provider-apply-results-from-plan var\provider-apply-plan-context-2026-07-04.json --execute-provider-apply-commands --json-out var\provider-apply-results-context-blockers-2026-07-04.json`
  - Expected exit: `1`
  - Result: `provider_apply_results_recorded=False`, execution mode `execute`, `plan_ready_to_apply=False`, commands `22`, provider preflight blockers `4`, project context missing `3`, failed commands `22`.
  - Each provider command was recorded as `status=blocked` before provider CLI execution.
- `python scripts\external_gate_handoff.py --verify-provider-apply-results var\provider-apply-results-context-blockers-2026-07-04.json --provider-apply-plan var\provider-apply-plan-context-2026-07-04.json --json-out var\provider-apply-results-verify-context-blockers-2026-07-04.json`
  - Expected exit: `1`
  - Result: `provider_apply_results_ok=False`, `plan_ready_to_apply=False`, `all_commands_succeeded=False`, expected commands `22`, reported commands `22`, command failures `22`, provider preflight blockers `4`, project context missing `3`, failures `5`, secret markers `0`.
- `python scripts\external_gate_handoff.py --verify-provider-apply-workflow var\provider-apply-plan-context-2026-07-04.json --provider-apply-results var\provider-apply-results-context-blockers-2026-07-04.json --promotion-receipt var\post-apply-promotion-receipt-project-context-chain-2026-07-04.json --require-promotion-go --json-out var\provider-apply-workflow-context-blockers-2026-07-04.json --markdown-out var\provider-apply-workflow-context-blockers-2026-07-04.md`
  - Expected exit: `1`
  - Result: `provider_apply_workflow_ok=False`, `ready_to_apply=False`, `all_commands_succeeded=False`, `promotion_receipt_ok=False`, provider preflight blockers `4`, project context missing `3`, failures `7`, promotion blocking reasons `17`.
  - Markdown includes `Provider preflight blockers: 4`, `Provider project context missing: 3`, plan blocking reasons, and provider blockers for Railway and Vercel.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-apply-results-context-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The apply-results and workflow layers now preserve these blockers instead of allowing a success-shaped receipt to obscure them.

## Next Cycle

Continue from the operator-facing GitHub workflow surface by ensuring the workflow artifact outputs are easy to consume in CI summaries and downstream release automation.
