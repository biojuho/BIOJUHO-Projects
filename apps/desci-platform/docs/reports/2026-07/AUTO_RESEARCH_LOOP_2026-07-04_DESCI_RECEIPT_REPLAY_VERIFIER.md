# AutoResearch Loop: DeSci Receipt Replay Verifier

Date: 2026-07-04

## Objective

Make the DeSci post-apply launch promotion receipt independently replayable so CI or an operator can distinguish a valid no-go receipt from a corrupted receipt, and can separately require a final go decision.

## Scope and Owned Paths

- `scripts/post_apply_evidence_gate.py`
- `scripts/external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions exit codes are the native automation signal for pass/fail outcomes.
  - https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes
- GitHub protected branches can require status checks to pass before merge.
  - https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- SLSA artifact verification guidance expects consumers to compare artifacts against expected identities and policy before trust.
  - https://slsa.dev/spec/v1.0/verifying-artifacts
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep the receipt as a generated artifact only.
  - Rejected because downstream systems still need custom logic to tell whether `no-go` is a valid fail-closed receipt or a corrupted artifact set.
- Variant B: add `--verify-promotion-receipt` and an explicit `--require-go` option.
  - Adopted because it keeps integrity replay separate from launch approval. A current no-go receipt can verify cleanly, while a release job can still fail with `--require-go`.

## Implementation

- `post_apply_evidence_gate.py`
  - Added `verify_promotion_receipt`.
  - Added CLI mode `--verify-promotion-receipt`.
  - Added `--require-go` for CI/status-check use.
  - The verifier validates receipt schema, check booleans, decision/phase consistency, blocker counts, referenced artifact existence, referenced artifact JSON shape, referenced artifact secret markers, and referenced artifact summaries.
- `external_gate_handoff.py`
  - Added receipt replay output paths:
    - `var/post-apply-promotion-receipt-verify.json`
    - `var/post-apply-promotion-receipt-require-go.json`
  - Added operator commands:
    - receipt integrity replay
    - receipt replay requiring final `go`

## Evidence

- Source/radar refresh:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-continuation.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_CONTINUATION.md` -> valid, 8 sources adopted.
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 37 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 107 passed.
- Current no-go receipt replay:
  - `python scripts/post_apply_evidence_gate.py --verify-promotion-receipt var/post-apply-promotion-receipt-receipt-verify-current-nogo-2026-07-04.json --json-out var/post-apply-promotion-receipt-verify-current-nogo-2026-07-04.json`
  - result: `ok=True`, `promotion_receipt_ok=False`, `release_decision=no-go`, `artifact_failures=0`, `secret_markers=0`, `failures=0`.
- Current no-go receipt require-go:
  - `python scripts/post_apply_evidence_gate.py --verify-promotion-receipt var/post-apply-promotion-receipt-receipt-verify-current-nogo-2026-07-04.json --require-go --json-out var/post-apply-promotion-receipt-require-go-current-nogo-2026-07-04.json`
  - expected result: `ok=False`, `failures=1`, blocker `promotion receipt ok must be true`.
- Generated handoff/apply-plan evidence includes the new replay commands:
  - `var/external-gate-handoff-receipt-verify-2026-07-04.json`
  - `var/external-gate-handoff-receipt-verify-2026-07-04.md`
  - `var/external-gate-provider-receipt-verify-index-2026-07-04.json`
  - `var/external-gate-provider-receipt-verify-2026-07-04.json`
  - `var/external-gate-provider-receipt-verify-2026-07-04.md`
- Secret-shape scan over generated receipt-replay artifacts returned no matches.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-receipt-verify-2026-07-04.json --trace-on-failure-dir var/traces/receipt-verify-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-receipt-verify-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The replay verifier improves release automation, but it does not bypass the real external blocker. Public promotion still requires provider/deploy evidence to produce:

- `post_apply_evidence_gate.ok=true`
- `evidence_manifest.ok=true`
- `evidence_manifest_verification.ok=true`
- `post_apply_promotion_receipt.ok=true`
- `post_apply_promotion_receipt_require_go.ok=true`

Current external evidence remains no-go because deploy/provider values and authenticated provider checks have not been applied.
