# AutoResearch Loop: DeSci Provider Workflow Outputs

Date: 2026-07-04

## Objective

Make the DeSci provider apply workflow verifier usable by downstream GitHub Actions steps. The previous verifier surfaces JSON, Markdown, job summary, and annotations; this loop adds opt-in `GITHUB_OUTPUT` parameters so CI can branch on the verified release state without parsing JSON in later steps.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions workflow commands support setting step output parameters by appending `name=value` records to the `GITHUB_OUTPUT` environment file.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions supports multiline output values through the same environment-file delimiter technique used for multiline environment variables.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions job summaries use `GITHUB_STEP_SUMMARY`; this remains the human-readable companion to the new machine-readable output.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep JSON, Markdown, job summary, and annotations only.
  - Rejected as incomplete for CI automation because downstream steps still need to parse JSON to decide whether provider apply workflow promotion can proceed.
- Variant B: add opt-in GitHub Actions output parameters to the workflow verifier.
  - Adopted because it preserves fail-closed JSON/exit-code behavior while exposing stable string values for `steps.<id>.outputs.*` conditions.

## Implementation

- Added `append_github_output()` with `name=value` records and delimiter-form multiline support.
- Added `provider_apply_workflow_github_outputs()` with stable output keys:
  - `provider_apply_workflow_ok`
  - `provider_apply_workflow_phase`
  - `provider_apply_workflow_ready_to_apply`
  - `provider_apply_workflow_all_commands_succeeded`
  - `provider_apply_workflow_promotion_receipt_ok`
  - `provider_apply_workflow_failure_count`
  - `provider_apply_workflow_results_command_failure_count`
  - provider plan, results, and promotion receipt paths.
- Added `--github-output` to `--verify-provider-apply-workflow`.
- Added guardrails so `--github-output` is only accepted in workflow verification mode and requires `GITHUB_OUTPUT`.
- Added tests for output mapping, multiline output writing, CLI output file writing, and invalid flag/env usage.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-workflow-outputs.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_WORKFLOW_OUTPUTS.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 50 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 189 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Workflow verifier with JSON, Markdown, step summary, annotations, and GitHub outputs:
  - `ok=false`, `operator_phase=provider_apply_workflow_blocked`.
  - `ready_to_apply=false`, `all_commands_succeeded=false`, `promotion_receipt_ok=false`.
  - `failure_count=5`, `results_command_failure_count=22`.
  - `var/external-gate-provider-workflow-outputs-2026-07-04-github-output.txt` includes `provider_apply_workflow_ok=false`, `provider_apply_workflow_failure_count=5`, and `provider_apply_workflow_results_command_failure_count=22`.
- Secret-shape scan over generated workflow-output artifacts:
  - Result: no secret-shaped values found. Uppercase environment key names such as `PRIVATE_KEY` were not treated as leaked values.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8081 --frontend http://127.0.0.1:5195 --json-out var/desci-product-smoke-workflow-outputs-2026-07-04.json`
  - 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5195 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-workflow-outputs-2026-07-04.json --trace-on-failure-dir var/traces/workflow-outputs-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-workflow-outputs-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The provider workflow gate is now machine-readable, human-readable, job-summary ready, annotation-ready, and downstream-CI-output ready. Public promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
