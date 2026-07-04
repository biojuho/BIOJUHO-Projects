# AutoResearch Loop - DeSci Operator Command Sync - 2026-07-04

## Objective

Verify that `operator_command_summary` stays synchronized with the detailed provider apply-plan command metadata.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_OPERATOR_COMMAND_SYNC.md`

## Source Evidence

- Railway and Vercel provider operations remain blocked by authenticated project context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Prior local cycle added `operator_command_summary` to the provider apply-plan handoff.

## A/B Hypothesis

- Baseline A: generate `operator_command_summary` without verifying it.
  - Rejected because the summary could drift from the detailed command metadata and mislead CI consumers.
- Variant B: rebuild the expected summary from detailed metadata during apply-plan verification and fail on mismatches.
  - Adopted because it keeps concise and detailed command surfaces aligned.

## Implementation

- Added `_operator_command_summary_verification()`.
- `verify_provider_apply_plan()` now validates summary entries when `operator_command_summary` is present.
- Verification compares `id`, `label`, `command`, `json_out`, and `success_condition`.
- Verification output now includes:
  - `summary.operator_command_count`
  - `summary.operator_command_failure_count`
  - `operator_command_summary_verification`
- Added a drift regression test that mutates a command and expects verification failure.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `60 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `115 passed`
- `python scripts\external_gate_handoff.py --verify-provider-apply-plan var\provider-apply-plan-operator-command-summary-2026-07-04.json --json-out var\provider-apply-plan-operator-command-summary-verify-2026-07-04.json`
  - Result: `provider_apply_plan_ok=True`, `ready_to_apply=False`, provider preflight blockers `4`, project context missing `3`, provider failures `0`, failures `0`, secret markers `0`.
  - JSON summary: operator commands `8`, operator command failures `0`.
  - `operator_command_summary_verification`: expected `8`, reported `8`, checked `8`, command failures `0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-operator-command-summary-sync-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

This cycle keeps command summaries mechanically aligned while preserving the no-go launch decision.

## Next Cycle

Continue by surfacing operator command-summary counts in console output and downstream status artifacts, so drift is visible without opening the JSON verifier.
