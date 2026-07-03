# AutoResearch Loop: DeSci Provider Workflow Summary

Date: 2026-07-04

## Objective

Make the DeSci provider apply workflow verifier easier to use in CI and release review. The prior verifier emitted JSON and console output, but GitHub Actions operators still had to open artifacts or logs to understand why promotion was blocked.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions job summaries support GitHub-flavored Markdown through `GITHUB_STEP_SUMMARY`.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions artifacts are the supported way to store and share workflow evidence after a run.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- `actions/upload-artifact` is the official artifact upload action repository.
  - https://github.com/actions/upload-artifact
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep provider workflow verification as JSON plus console output.
  - Rejected because CI and release reviewers still need to open logs or parse JSON to see the blocking reason.
- Variant B: emit a concise Markdown workflow verification report and optionally append it to `GITHUB_STEP_SUMMARY`.
  - Adopted because it preserves the machine-readable JSON gate while adding a CI-native human summary and artifact-ready Markdown.

## Implementation

- Added `render_provider_apply_workflow_verification_markdown()`.
- Added `--markdown-out` support for `--verify-provider-apply-workflow`.
- Added `--github-step-summary`, which appends the same Markdown to `GITHUB_STEP_SUMMARY`.
- Added fail-fast CLI validation when `--github-step-summary` is used without `GITHUB_STEP_SUMMARY`.
- Added workflow Markdown tests for blocked artifact resolution, successful summary output, and missing-summary-env validation.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-workflow-summary.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_WORKFLOW_SUMMARY.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 42 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 181 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Workflow verifier with Markdown and GitHub step summary:
  - `ok=false`, `operator_phase=provider_apply_workflow_blocked`.
  - `artifact_resolution={"provider_apply_results_json":"plan_metadata","promotion_receipt_json":"plan_metadata"}`.
  - `ready_to_apply=false`, `all_commands_succeeded=false`, `promotion_receipt_ok=false`.
  - `failure_count=5`, `results_command_failure_count=22`.
  - Markdown output matched the generated step-summary file.
- Secret-shape scan over generated workflow-summary artifacts:
  - scanned=13, findings=0.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8079 --frontend http://127.0.0.1:5193 --json-out var/desci-product-smoke-workflow-summary-2026-07-04.json`
  - 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5193 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-workflow-summary-2026-07-04.json --trace-on-failure-dir var/traces/workflow-summary-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-workflow-summary-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The verifier now provides machine JSON, artifact-ready Markdown, and GitHub job-summary output. Public promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
