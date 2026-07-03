# AutoResearch Loop: DeSci Provider Workflow Default Paths

Date: 2026-07-04

## Objective

Reduce operator error in the DeSci private-provider apply workflow. The previous workflow verifier could prove the complete apply path, but the operator still had to pass the provider apply results path and promotion receipt path every time.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions fail a step when a command exits non-zero, so the verifier remains suitable as a CI gate.
  - https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- GitHub Actions artifacts are the official path for storing and sharing workflow evidence after a run.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: require the operator to pass `--provider-apply-results` and `--promotion-receipt` every time.
  - Rejected because the verifier is correct but the command is longer and easier to run against the wrong artifact.
- Variant B: resolve provider apply results and promotion receipt paths from the apply plan metadata by default.
  - Adopted because the operator can now run one plan-centered verifier command while explicit path flags still work when needed.

## Implementation

- Added plan-metadata artifact path resolution to `verify_provider_apply_workflow()`.
- Added `artifact_resolution` to workflow verification JSON so reviewers can see whether paths came from CLI arguments, plan metadata, or fallback defaults.
- Added default workflow commands to provider apply plan JSON and Markdown:
  - `default_verify_command`
  - `default_require_go_command`
- Preserved the explicit `--provider-apply-results` and `--promotion-receipt` commands for override workflows.
- Added API and CLI tests for plan-default artifact resolution.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-next-cycle.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_NEXT_CYCLE.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 39 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 178 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Default-path recorder receipt:
  - `execution_mode=dry_run`, `command_count=22`, `failed_commands=22`, `ok=false`.
- Default-path workflow verifier:
  - Command omitted `--provider-apply-results` and `--promotion-receipt`.
  - `ok=false`, `operator_phase=provider_apply_workflow_blocked`.
  - `artifact_resolution={"provider_apply_results_json":"plan_metadata","promotion_receipt_json":"plan_metadata"}`.
  - `ready_to_apply=false`, `all_commands_succeeded=false`, `promotion_receipt_ok=false`, `failure_count=5`.
- Secret-shape scan over generated workflow-default artifacts:
  - scanned=11, findings=0.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8078 --frontend http://127.0.0.1:5192 --json-out var/desci-product-smoke-workflow-defaults-2026-07-04.json`
  - 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-workflow-defaults-2026-07-04.json --trace-on-failure-dir var/traces/workflow-defaults-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-workflow-defaults-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The local workflow gate is simpler and still fail-closed. Public promotion remains no-go until private provider values are applied and the post-apply promotion receipt is generated as go. The next operator command after real provider apply evidence exists is now:

```powershell
python scripts/external_gate_handoff.py --verify-provider-apply-workflow var/external-gate-provider-workflow-defaults-2026-07-04.json --require-promotion-go --json-out var/external-gate-provider-workflow-defaults-2026-07-04-workflow-verify.json
```
