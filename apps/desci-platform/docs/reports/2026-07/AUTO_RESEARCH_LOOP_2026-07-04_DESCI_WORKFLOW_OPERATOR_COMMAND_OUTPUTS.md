# AutoResearch Loop - DeSci Workflow Operator Command Outputs - 2026-07-04

## Objective

Surface provider apply operator command-summary counts through the provider apply workflow verifier, Markdown report, GitHub outputs, and console summary so CI/status consumers can see command-chain drift without opening the nested apply-plan verifier JSON.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_WORKFLOW_OPERATOR_COMMAND_OUTPUTS.md`

## Source Evidence

- Upstream comparison reference: `https://github.com/Veritas-7/autoresearch-skill-system.git` main/HEAD at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Railway CLI docs still require authenticated CLI context and expose project management commands including `link` and `status`.
  - https://docs.railway.com/cli
- Vercel CLI docs still require login or `VERCEL_TOKEN` for automated access, and project linking binds a local directory to the intended Vercel project.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking

## A/B Hypothesis

- Baseline A: keep operator command-summary counts only in apply-plan verification JSON and the apply-plan console.
  - Rejected because the provider apply workflow is the handoff object CI and operators consume after apply-results and promotion checks are wired.
- Variant B: propagate the apply-plan verifier's `operator_command_count` and `operator_command_failure_count` into workflow JSON, Markdown, GitHub outputs, and console output.
  - Adopted because it keeps the workflow as the concise status artifact while preserving nested verifier detail.

## Implementation

- `verify_provider_apply_workflow()` now copies command-summary counts from `provider_apply_plan_verification.summary`.
- Workflow verification JSON now includes top-level and `summary` fields:
  - `operator_command_count`
  - `operator_command_failure_count`
- Workflow Markdown now prints both counts in the Status table.
- Workflow GitHub outputs now include:
  - `provider_apply_workflow_operator_command_count`
  - `provider_apply_workflow_operator_command_failure_count`
- Workflow console output now prints:
  - `operator_commands`
  - `operator_command_failures`
- Focused tests cover JSON fields, Markdown rows, GitHub output keys, CLI output text, and console printing.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `62 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `117 passed`
- `python scripts\external_gate_handoff.py --record-provider-apply-results-from-plan var\provider-apply-plan-operator-command-summary-2026-07-04.json --execute-provider-apply-commands --json-out var\provider-apply-plan-operator-command-summary-workflow-output-results-2026-07-04.json`
  - Expected exit: `1`
  - Result: blocked receipt written; `plan_ready_to_apply=False`, `command_count=22`, provider preflight blockers `4`, project context missing `3`, failed commands `22`.
- Workflow GitHub-output command:
  - `GITHUB_OUTPUT=var\provider-apply-plan-operator-command-summary-workflow-output-github-output-2026-07-04.txt`
  - `python scripts\external_gate_handoff.py --verify-provider-apply-workflow var\provider-apply-plan-operator-command-summary-2026-07-04.json --provider-apply-results var\provider-apply-plan-operator-command-summary-workflow-output-results-2026-07-04.json --promotion-receipt var\post-apply-promotion-receipt-project-context-chain-2026-07-04.json --require-promotion-go --json-out var\provider-apply-plan-operator-command-summary-workflow-output-2026-07-04.json --markdown-out var\provider-apply-plan-operator-command-summary-workflow-output-2026-07-04.md --github-output`
  - Result: workflow remains no-go with `provider_apply_workflow_ok=False`, `operator_commands=8`, `operator_command_failures=0`, failures `7`, next required actions `4`, promotion blocking reasons `17`.
  - Wrote JSON, Markdown, and GitHub output artifacts.
- `python scripts\external_gate_handoff.py --verify-provider-apply-workflow-github-output var\provider-apply-plan-operator-command-summary-workflow-output-github-output-2026-07-04.txt --provider-apply-workflow-json var\provider-apply-plan-operator-command-summary-workflow-output-2026-07-04.json --json-out var\provider-apply-plan-operator-command-summary-workflow-output-github-output-verify-2026-07-04.json`
  - Result: `provider_apply_workflow_github_output_ok=True`, expected outputs `24`, parsed outputs `24`, checked outputs `24`, mismatched outputs `0`, failures `0`, secret markers `0`.
- Artifact spot-check:
  - Workflow JSON has `operator_command_count=8` and `operator_command_failure_count=0` at top level and in summary.
  - Workflow Markdown has `| Operator commands | 8 |` and `| Operator command failures | 0 |`.
  - GitHub output has `provider_apply_workflow_operator_command_count=8` and `provider_apply_workflow_operator_command_failure_count=0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-workflow-operator-command-output-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.
  - Note: the shell call timed out at 180s, but the smoke process completed and wrote the passing JSON after `332396 ms`.

## Current Launch Boundary

Public launch remains externally blocked:

- Provider templates still contain blanks and must be filled in a private local directory.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- Promotion receipt remains no-go until provider checks pass and post-apply evidence is regenerated.

This cycle improves workflow/status observability only. It does not weaken the no-go release decision.

## Next Cycle

Continue by checking whether these workflow operator command counts should feed the active operator status rollup or release dashboard artifact.
