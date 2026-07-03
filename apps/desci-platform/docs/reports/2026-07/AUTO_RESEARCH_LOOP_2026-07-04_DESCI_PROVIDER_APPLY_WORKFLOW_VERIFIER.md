# AutoResearch Loop: DeSci Provider Apply Workflow Verifier

Date: 2026-07-04

## Objective

Close the remaining local launch-control gap after provider apply plan verification, provider apply result recording, and provider apply result verification. Operators need one machine-readable workflow gate that proves the whole private-provider apply sequence is complete before promotion can proceed.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions fail a workflow step when a process exits with a non-zero code.
  - https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- Python `pathlib.Path.exists()` is the standard path-existence check used by the workflow verifier for optional artifacts.
  - https://docs.python.org/3/library/pathlib.html
- Python `json` preserves input and output order by default, which keeps generated evidence stable for operator review.
  - https://docs.python.org/3/library/json.html
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep apply-plan readiness, apply-results verification, and promotion receipt verification as separate operator steps.
  - Rejected because an operator or CI job can accidentally skip one step before promotion.
- Variant B: add a single end-to-end provider apply workflow verifier.
  - Adopted because it composes the existing gates and fails closed unless the plan is ready, all provider apply commands succeeded, and the post-apply promotion receipt is verified as go.

## Implementation

- Added `provider_apply_workflow_verification` metadata to generated provider apply plans and Markdown.
- Added `--verify-provider-apply-workflow`.
- Added `--provider-apply-results`, `--promotion-receipt`, and `--require-promotion-go` workflow verification flags.
- Added `verify_provider_apply_workflow()` to compose:
  - `provider_apply_plan_verification.ready_to_apply=true`
  - `provider_apply_results_verification.ok=true`
  - `provider_apply_results.all_commands_succeeded=true`
  - `post_apply_promotion_receipt.ok=true`
- Added fail-closed missing-artifact handling for provider apply results and promotion receipt JSON.
- Added CLI validation so workflow artifact flags cannot be used without `--verify-provider-apply-workflow`.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --latest-observed-commit Veritas-7/autoresearch-skill-system=b8bbf393759d6e67e780f03c572ec626fab6593b --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-apply-workflow.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_APPLY_WORKFLOW.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 37 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 133 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 176 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Recorder dry-run receipt:
  - `execution_mode=dry_run`, `command_count=22`, `provider_count=4`, `failed_commands=22`, `ok=false`.
- Workflow verifier against current blocked artifacts:
  - `ok=false`, `operator_phase=provider_apply_workflow_blocked`.
  - `ready_to_apply=false`, `all_commands_succeeded=false`, `promotion_receipt_ok=false`.
  - `failure_count=5`.
  - Failures: provider apply plan not ready, provider apply results not successful, provider apply results do not have `all_commands_succeeded=true`, post-apply promotion receipt verification failed, post-apply promotion receipt is not go.
- Secret-shape scan over generated provider apply workflow artifacts:
  - scanned=11, findings=0.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8077 --frontend http://127.0.0.1:5191 --json-out var/desci-product-smoke-provider-apply-workflow-2026-07-04.json`
  - 5/5 passed; fixture still reports `/ready status=blocked` and `/launch decision=no-go`.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5191 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-apply-workflow-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-workflow-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-apply-workflow-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The local launch-control path now has a single workflow verifier for the private provider apply sequence:

- verify provider apply plan
- record provider apply results
- verify provider apply results
- verify post-apply promotion receipt
- require promotion receipt go before release promotion

Public promotion is still no-go because the private provider values have not been applied to GitHub, Railway, Vercel, and Amoy. The workflow verifier is intentionally blocked until real provider apply results succeed and a go promotion receipt is generated.
