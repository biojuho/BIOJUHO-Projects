# AutoResearch Loop: DeSci Promotion Receipt

Date: 2026-07-04

## Objective

Make the DeSci post-apply launch promotion path produce one compact machine-readable receipt that an operator or CI job can use as the final go/no-go decision after provider values are applied.

## Scope and Owned Paths

- `scripts/post_apply_evidence_gate.py`
- `scripts/external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub environments require jobs to satisfy protection rules before running or accessing environment secrets.
  - https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- GitHub custom deployment protection rules can automatically gate environment-targeting workflow jobs.
  - https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/configure-custom-protection-rules
- GitHub required status checks must pass before protected branch changes can merge.
  - https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub Actions exit codes drive check run success or failure.
  - https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes
- SLSA verification guidance expects consumers to compare artifact/provenance details against configured expectations.
  - https://slsa.dev/spec/v1.0/verifying-artifacts
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Decision

- Baseline A: keep gate JSON, manifest JSON, and verification JSON as separate outputs only.
  - Rejected because CI or an operator still has to interpret three files and infer the final launch decision.
- Variant B: add `--promotion-receipt-out` to the single post-apply command.
  - Adopted because it preserves the underlying artifacts while emitting one deterministic decision JSON with checks, paths, blocker counts, and no-go reasons.

## Implementation

- `post_apply_evidence_gate.py`
  - Added `build_promotion_receipt`.
  - Added `--promotion-receipt-out` in external-gate mode.
  - Receipt generation requires `--json-out`, `--manifest-out`, and `--verify-manifest-out`, returning exit code 2 when the operator asks for an incomplete receipt.
  - Receipt `ok` requires `post_apply_evidence_gate`, `evidence_manifest`, and `evidence_manifest_verification` to all be true.
- `external_gate_handoff.py`
  - Added `promotion_receipt_json_out`.
  - Updated the promotion single command to write `var/post-apply-promotion-receipt.json`.
  - Updated the success condition to include `post_apply_promotion_receipt.ok=true`.

## Evidence

- `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 32 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 102 passed.
- Generated current no-go promotion receipt evidence:
  - `var/post-apply-evidence-gate-promotion-receipt-current-nogo-2026-07-04.json`
  - `var/post-apply-evidence-manifest-promotion-receipt-current-nogo-2026-07-04.json`
  - `var/post-apply-evidence-manifest-verify-promotion-receipt-current-nogo-2026-07-04.json`
  - `var/post-apply-promotion-receipt-current-nogo-2026-07-04.json`
- Current receipt summary:
  - `ok=false`
  - `release_decision=no-go`
  - `operator_phase=post_apply_launch_blocked`
  - `blocking_reason_count=11`
  - `verification_artifact_failure_count=0`
  - `verification_digest_mismatch_count=0`
  - `verification_secret_marker_count=0`
  - first blocker: `external gate ok must be true`
- Generated handoff/apply-plan evidence includes the new receipt path and single promotion command:
  - `var/external-gate-handoff-promotion-receipt-2026-07-04.json`
  - `var/external-gate-handoff-promotion-receipt-2026-07-04.md`
  - `var/external-gate-provider-promotion-receipt-index-2026-07-04.json`
  - `var/external-gate-provider-promotion-receipt-2026-07-04.json`
  - `var/external-gate-provider-promotion-receipt-2026-07-04.md`
- Secret-shape scan over generated promotion-receipt artifacts returned no matches.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-promotion-receipt-2026-07-04.json --trace-on-failure-dir var/traces/promotion-receipt-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - first attempt timed out at the command wrapper after 124 seconds.
  - rerun: `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-promotion-receipt-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The local launch path remains green, but public promotion is still no-go until external provider values/auth are applied and the post-apply promotion command returns:

- `post_apply_evidence_gate.ok=true`
- `evidence_manifest.ok=true`
- `evidence_manifest_verification.ok=true`
- `post_apply_promotion_receipt.ok=true`

Current external gate evidence still reports deploy/provider readiness blockers, so the correct behavior is fail-closed no-go with a clean receipt.
