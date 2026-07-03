# AutoResearch Loop: DeSci Post-Apply Evidence Manifest

Date: 2026-07-04

## External Research

- GitHub Actions artifact guidance separates generated workflow data from later download/review: https://docs.github.com/en/actions/tutorials/store-and-share-data
- SLSA artifact verification guidance treats provenance and artifact identity as a later verifier input: https://slsa.dev/spec/v1.0/verifying-artifacts
- GitHub artifact attestations document provenance checks for build artifacts: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds

## A/B Decision

- A: Keep only `post_apply_evidence_gate.ok=true`.
  - Rejected because a later reviewer cannot confirm which evidence files were inspected without re-reading mutable paths.
- B: Add a post-apply evidence manifest with file roles, sha256, byte size, required/missing state, secret-marker scan state, and promotion-gate status.
  - Selected because it preserves the existing fail-closed gate while making the exact artifact set reproducible.

## Implementation

- `scripts/post_apply_evidence_gate.py`
  - Added `--manifest-out`.
  - Added evidence artifact entries with `role`, `path`, `exists`, `bytes`, `sha256`, `secret_marker_names`, `secret_marker_count`, and `ok`.
  - Manifest `ok` requires the post-apply gate to be true, all required artifacts to exist, and zero secret-shaped markers.
- `scripts/external_gate_handoff.py`
  - Provider apply plans now include `promotion_manifest_json_out`.
  - The promotion gate command now writes both `var/post-apply-evidence-gate.json` and `var/post-apply-evidence-manifest.json`.

## Evidence

- Focused compile: `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py`
- Focused tests: `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 21 passed.
- Release/provider/product tests: `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 91 passed.
- Browser launch-click suite: `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-post-apply-manifest-2026-07-04.json --trace-on-failure-dir var/traces/post-apply-manifest-2026-07-04` -> 9/9 passed.
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-post-apply-manifest-2026-07-04.json` -> 8/8 passed.
- Generated current no-go gate evidence:
  - `var/post-apply-evidence-gate-current-nogo-manifest-2026-07-04.json`
  - `var/post-apply-evidence-manifest-current-nogo-2026-07-04.json`
- No-go manifest result: artifact_count=2, missing_required_count=0, secret_marker_count=0, failed_artifact_count=0, promotion_gate_ok=false.
- New handoff output includes `--manifest-out var/post-apply-evidence-manifest.json` in the promotion command.

## Current Blocker

The local product and guardrails pass, but public launch promotion remains no-go until external provider values/auth are applied and the aggregate post-apply external release gate reports:

- deploy_failed=0
- provider_failed_checks=0
- provider_ready == provider_count
- `post_apply_evidence_gate.ok=true`
- `evidence_manifest.ok=true`
