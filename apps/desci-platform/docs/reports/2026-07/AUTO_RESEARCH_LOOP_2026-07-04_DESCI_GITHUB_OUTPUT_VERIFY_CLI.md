# AutoResearch Loop - DeSci GitHub Output Verify CLI - 2026-07-04

## Objective

Expose provider apply workflow GitHub-output verification as a CLI mode so CI can validate generated outputs without a Python one-liner.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_GITHUB_OUTPUT_VERIFY_CLI.md`

## Source Evidence

- Railway and Vercel provider operations still depend on authenticated and project-linked CLI context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local workflow GitHub outputs now have a parser/verifier; the remaining gap was operator-friendly CLI access.

## Baseline

- `verify_provider_apply_workflow_github_output()` could validate a GitHub-output file from Python.
- CI operators would need an inline Python command to invoke it.
- Existing CLI modes covered plan, results, workflow, and provider output generation, but not GitHub-output verification.

## A/B Decision

- Baseline A: leave the verifier as a library helper.
  - Rejected because CI YAML and operator scripts should use a stable CLI contract.
- Variant B: add `--verify-provider-apply-workflow-github-output` with `--provider-apply-workflow-json`.
  - Adopted because it reuses the tested verifier and returns normal CLI exit codes.

## Implementation

- Added CLI arguments:
  - `--verify-provider-apply-workflow-github-output`
  - `--provider-apply-workflow-json`
- Added validation that the GitHub-output verifier mode requires a workflow JSON path.
- Added mutual-exclusion handling with the other provider verification modes.
- Added console reporting for expected, parsed, checked, mismatched, failure, and secret-marker counts.
- Added optional `--json-out` evidence writing.
- Added CLI tests for success and missing workflow JSON.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `59 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `114 passed`
- `python scripts\external_gate_handoff.py --verify-provider-apply-workflow-github-output var\provider-apply-workflow-primary-blocker-github-output-2026-07-04.txt --provider-apply-workflow-json var\provider-apply-workflow-primary-blocker-2026-07-04.json --json-out var\provider-apply-workflow-github-output-verify-2026-07-04.json`
  - Result: `provider_apply_workflow_github_output_ok=True`, expected outputs `22`, parsed outputs `22`, checked outputs `22`, mismatched outputs `0`, failures `0`, secret markers `0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-github-output-cli-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

CI can now validate workflow GitHub outputs through the repo-owned CLI while the release correctly remains no-go.

## Next Cycle

Continue hardening launch automation by deciding whether workflow GitHub-output verification should be included in the generated handoff command set.
