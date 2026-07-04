# AutoResearch Loop - DeSci Operator Command Console - 2026-07-04

## Objective

Surface operator command-summary counts in provider apply-plan verifier console output so command drift is visible without opening verifier JSON.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_OPERATOR_COMMAND_CONSOLE.md`

## Source Evidence

- Railway and Vercel provider operations remain blocked by authenticated project context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Prior local cycle added `operator_command_summary_verification` to provider apply-plan verification.

## A/B Hypothesis

- Baseline A: keep command-summary verification counts only in JSON.
  - Rejected because operators running the CLI should see command drift immediately in console output.
- Variant B: add `operator_commands` and `operator_command_failures` to the apply-plan verifier console summary.
  - Adopted because it preserves JSON detail while improving fast terminal triage.

## Implementation

- Updated `print_provider_apply_plan_verification_report()` to print:
  - `operator_commands`
  - `operator_command_failures`
- Added a focused output test that captures the reporter output.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `61 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `116 passed`
- `python scripts\external_gate_handoff.py --verify-provider-apply-plan var\provider-apply-plan-operator-command-summary-2026-07-04.json --json-out var\provider-apply-plan-operator-command-summary-console-2026-07-04.json`
  - Result: `provider_apply_plan_ok=True`, `ready_to_apply=False`, provider preflight blockers `4`, project context missing `3`, provider failures `0`, `operator_commands=8`, `operator_command_failures=0`, failures `0`, secret markers `0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-operator-command-console-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The verifier now exposes command-summary drift at the console layer while preserving the no-go release decision.

## Next Cycle

Continue by checking whether the same operator command counts should be surfaced in workflow GitHub outputs or a downstream status artifact.
