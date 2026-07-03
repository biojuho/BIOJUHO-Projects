# AutoResearch Loop: DeSci Single Promotion Command

Date: 2026-07-04

## Objective

Make the DeSci post-apply launch promotion path harder to misuse by producing the gate report, evidence manifest, and manifest verification report from one command.

## Scope and Owned Paths

- `scripts/post_apply_evidence_gate.py`
- `scripts/external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions exit-code docs: CI/automation commands should use exit codes to mark pass/fail status.
  - https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- GitHub artifact attestations docs: artifact verification is a first-class consumer step and can be performed with GitHub CLI.
  - https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds
- SLSA verification guidance: artifact provenance must be inspected against expectations before trust.
  - https://slsa.dev/spec/v1.0/verifying-artifacts
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Decision

- Baseline A: keep two promotion commands:
  - generate `post-apply-evidence-gate.json` and `post-apply-evidence-manifest.json`
  - separately run `--verify-manifest`
  - Rejected because the launch path can accidentally skip the verification step.
- Variant B: add `--verify-manifest-out` so the promotion command writes all three artifacts and returns one exit status.
  - Adopted because it reduces operator error and preserves the independent `--verify-manifest` command for later audit/replay.

## Implementation

- `post_apply_evidence_gate.py`
  - Added `--verify-manifest-out` in external-gate mode.
  - The command now writes gate JSON, manifest JSON, and manifest verification JSON in one run when all three output paths are supplied.
  - `--verify-manifest-out` without `--manifest-out` returns exit code 2.
- `external_gate_handoff.py`
  - `promotion_gate_command` now includes `--verify-manifest-out var/post-apply-evidence-manifest-verify.json`.
  - Added `promotion_single_command` as an explicit operator-facing alias.
  - Markdown renders the single promotion command.

## Evidence

- `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 28 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 98 passed.
- Generated current no-go single-command evidence:
  - `var/post-apply-evidence-gate-single-promotion-current-nogo-2026-07-04.json`
  - `var/post-apply-evidence-manifest-single-promotion-current-nogo-2026-07-04.json`
  - `var/post-apply-evidence-manifest-verify-single-promotion-current-nogo-2026-07-04.json`
- Current no-go verifier summary:
  - `ok=false`
  - `manifest_ok=false`
  - `promotion_gate_ok=false`
  - `artifact_failure_count=0`
  - `digest_mismatch_count=0`
  - `missing_required_count=0`
  - `secret_marker_count=0`
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-single-promotion-2026-07-04.json --trace-on-failure-dir var/traces/single-promotion-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-single-promotion-2026-07-04.json`
  - 8/8 passed.
- Secret-shape scan over generated single-promotion artifacts returned no matches.

## Current Launch Blocker

The local launch path is green, but public promotion remains no-go until external provider values/auth are applied and the single promotion command returns:

- `post_apply_evidence_gate.ok=true`
- `evidence_manifest.ok=true`
- `evidence_manifest_verification.ok=true`

Current external gate remains no-go because external deploy/provider readiness has not been applied.
