# AutoResearch Loop - DeSci Operator Command Summary - 2026-07-04

## Objective

Expose the provider apply-plan command chain in a concise operator summary so CI and operators can find the workflow GitHub-output commands without parsing detailed handoff sections.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_OPERATOR_COMMAND_SUMMARY.md`

## Source Evidence

- Railway and Vercel provider operations remain blocked by authenticated project context.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Prior local cycle added GitHub-output command generation and verification commands to the detailed workflow metadata.

## A/B Hypothesis

- Baseline A: keep commands only in detailed apply-plan sections.
  - Rejected because status consumers need a compact command list without scanning several sections.
- Variant B: add a top-level `operator_command_summary` list and render it near `Operator Status`.
  - Adopted because it preserves detailed metadata while making the command chain directly consumable.

## Implementation

- Added `_operator_command_summary()`.
- Added top-level `operator_command_summary` to provider apply-plan JSON.
- Summary entries include `id`, `label`, `command`, `json_out`, and `success_condition`.
- Included command entries for:
  - apply-plan verification
  - require-ready apply-plan verification
  - provider apply-results recording
  - provider apply-results verification
  - provider apply workflow verification
  - workflow GitHub-output writing
  - workflow GitHub-output verification
  - post-apply evidence promotion
- Added Markdown `Operator Command Summary`.
- Updated tests to assert summary IDs and the workflow GitHub-output verifier command.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `59 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `114 passed`
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-project-context-chain-2026-07-04.json --json-out var\external-gate-handoff-operator-command-summary-2026-07-04.json --markdown-out var\external-gate-handoff-operator-command-summary-2026-07-04.md --provider-template-dir var\provider-templates-operator-command-summary-2026-07-04 --provider-template-index-out var\provider-template-index-operator-command-summary-2026-07-04.json --provider-apply-plan-out var\provider-apply-plan-operator-command-summary-2026-07-04.json --provider-apply-plan-markdown-out var\provider-apply-plan-operator-command-summary-2026-07-04.md`
  - Expected exit: `1`
  - Result: generated no-go handoff, provider templates, provider template index, provider apply-plan JSON, and provider apply-plan Markdown.
  - `operator_command_summary` contains `write_workflow_github_output` and `verify_workflow_github_output`.
  - Markdown contains `Operator Command Summary` with the GitHub-output write and verify commands.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-operator-command-summary-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

This cycle improves operator command discoverability and preserves the release no-go.

## Next Cycle

Continue by adding a small verifier that checks `operator_command_summary` commands remain synchronized with the detailed workflow metadata.
