# AutoResearch Loop - DeSci GitHub Output Command Set - 2026-07-04

## Objective

Add the provider apply workflow GitHub-output generation and verification commands to the generated provider apply-plan handoff, so operators and CI do not need to invent command wiring after the CLI verifier exists.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_GITHUB_OUTPUT_COMMAND_SET.md`

## Source Evidence

- Railway provider application still requires authenticated and project-linked CLI context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Vercel provider application still requires authenticated and project-linked CLI context.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Prior local cycle added `--verify-provider-apply-workflow-github-output`; this cycle wires that command into the generated handoff.

## A/B Hypothesis

- Baseline A: expose the CLI verifier but leave operators to assemble the GitHub-output file path and verification command manually.
  - Rejected because handoff consumers could drift from the canonical command or skip output verification.
- Variant B: generate the GitHub-output file path, output command, verification JSON path, and verification command directly in `provider_apply_workflow_verification`.
  - Adopted because the apply-plan handoff now contains the complete command chain.

## Implementation

- Added `github_output_path` and `github_output_verify_json_out` to generated provider apply workflow metadata.
- Added `github_output_powershell_command`, using the existing workflow require-go command plus `--github-output`.
- Added `github_output_verify_command`, using `--verify-provider-apply-workflow-github-output` and `--provider-apply-workflow-json`.
- Added Markdown output for the new paths and commands.
- Updated handoff tests to assert the generated command set and Markdown.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `59 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `114 passed`
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-project-context-chain-2026-07-04.json --json-out var\external-gate-handoff-github-output-command-2026-07-04.json --markdown-out var\external-gate-handoff-github-output-command-2026-07-04.md --provider-template-dir var\provider-templates-github-output-command-2026-07-04 --provider-template-index-out var\provider-template-index-github-output-command-2026-07-04.json --provider-apply-plan-out var\provider-apply-plan-github-output-command-2026-07-04.json --provider-apply-plan-markdown-out var\provider-apply-plan-github-output-command-2026-07-04.md`
  - Expected exit: `1`
  - Result: generated no-go handoff, provider templates, provider template index, provider apply-plan JSON, and provider apply-plan Markdown.
  - The apply-plan workflow metadata includes:
    - `github_output_path=var\provider-apply-plan-github-output-command-2026-07-04-workflow-verify-github-output.txt`
    - `github_output_verify_json_out=var\provider-apply-plan-github-output-command-2026-07-04-workflow-github-output-verify.json`
    - `github_output_powershell_command`
    - `github_output_verify_command`
- Generated GitHub-output command:
  - Expected exit: `1`
  - Result: no-go workflow wrote `var\provider-apply-plan-github-output-command-2026-07-04-workflow-verify.json` and `var\provider-apply-plan-github-output-command-2026-07-04-workflow-verify-github-output.txt`.
- Generated GitHub-output verifier command:
  - `python scripts\external_gate_handoff.py --verify-provider-apply-workflow-github-output var\provider-apply-plan-github-output-command-2026-07-04-workflow-verify-github-output.txt --provider-apply-workflow-json var\provider-apply-plan-github-output-command-2026-07-04-workflow-verify.json --json-out var\provider-apply-plan-github-output-command-2026-07-04-workflow-github-output-verify.json`
  - Result: `provider_apply_workflow_github_output_ok=True`, expected outputs `22`, parsed outputs `22`, checked outputs `22`, mismatched outputs `0`, failures `0`, secret markers `0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-github-output-command-set-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

This cycle improves the handoff command chain; it does not recast external provider blockers as launch-ready.

## Next Cycle

Continue hardening by making the generated provider apply-plan workflow command set available in concise operator status summaries, not only the detailed apply-plan Markdown.
