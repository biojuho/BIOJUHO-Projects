# AutoResearch Loop: DeSci Post-Apply Manifest Verifier

Date: 2026-07-04

## Objective

Advance DeSci launch hardening from "post-apply evidence manifest exists" to "launch reviewer can independently verify the manifest and artifact digests before promotion."

## Scope and Owned Paths

- `scripts/post_apply_evidence_gate.py`
- `scripts/external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub artifact attestations docs: artifact attestations establish where/how software was built and GitHub CLI verifies artifacts by path or digest.
  - https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- SLSA verification guidance: provenance only helps when a verifier inspects it against expectations.
  - https://slsa.dev/spec/v1.0/verifying-artifacts
- in-toto attestation framework: attestations are verifiable claims that consumers validate to establish supply-chain trust.
  - https://github.com/in-toto/attestation
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: Generate `post-apply-evidence-manifest.json` and require reviewers to inspect it manually.
  - Weakness: artifact tampering after manifest creation is not detected by a deterministic command.
- Variant B: Add `--verify-manifest` to recompute sha256/byte counts, reject missing artifacts, reject secret-shaped markers, and keep no-go manifests blocked even when artifact hashes are intact.
  - Decision: adopted. It improves launch evidence quality while staying offline, deterministic, and narrow.

## Implementation

- Added `verify_evidence_manifest()` and CLI mode:
  - `python scripts/post_apply_evidence_gate.py --verify-manifest var/post-apply-evidence-manifest.json --json-out var/post-apply-evidence-manifest-verify.json`
- The verifier checks:
  - manifest schema and `ok`
  - promotion gate state
  - artifact count consistency
  - current existence, byte size, sha256, and secret-shaped markers
  - malformed or unreadable artifact paths
- Updated provider apply plans:
  - success condition is now `post_apply_evidence_gate.ok=true and evidence_manifest_verification.ok=true`
  - post-apply evidence includes `promotion_manifest_verify_json_out`
  - Markdown includes the manifest verification command.

## Evidence

- `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 26 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 96 passed.
- Current no-go evidence generated:
  - `var/post-apply-evidence-gate-current-nogo-manifest-verifier-2026-07-04.json`
  - `var/post-apply-evidence-manifest-current-nogo-verifier-2026-07-04.json`
  - `var/post-apply-evidence-manifest-verify-current-nogo-2026-07-04.json`
- Current no-go verifier summary:
  - `ok=false`
  - `manifest_ok=false`
  - `promotion_gate_ok=false`
  - `artifact_failure_count=0`
  - `digest_mismatch_count=0`
  - `missing_required_count=0`
  - `secret_marker_count=0`
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-manifest-verifier-final-2026-07-04.json --trace-on-failure-dir var/traces/manifest-verifier-final-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-manifest-verifier-final-2026-07-04.json`
  - 8/8 passed.
- Secret-shape scan over generated handoff/gate/manifest/verify artifacts returned no matches.

## Current Launch Blocker

The product path and local guardrails are green, but public launch promotion remains blocked until external provider values/auth are applied and post-apply evidence verifies with:

- deploy_failed=0
- provider_failed_checks=0
- provider_ready == provider_count
- `post_apply_evidence_gate.ok=true`
- `evidence_manifest_verification.ok=true`

Current external gate remains no-go because deploy/provider external readiness has not been applied.
