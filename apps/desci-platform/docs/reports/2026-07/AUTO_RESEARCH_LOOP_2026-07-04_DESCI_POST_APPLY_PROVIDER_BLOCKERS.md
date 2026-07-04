# AutoResearch Loop: Post-Apply Provider Blockers

Date: 2026-07-04

## Objective

Make the post-apply launch promotion path preserve provider auth recovery
instructions when external release evidence is still no-go.

## Scope

Owned paths changed in this cycle:

- `scripts/post_apply_evidence_gate.py`
- `backend/tests/test_post_apply_evidence_gate.py`

The change does not weaken post-apply gating. It adds redacted provider blocker
details to failed evidence and promotion receipts while keeping all existing
count-based fail-closed checks.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern is durable no-go evidence with explicit operator actions,
not autonomous promotion when external provider proof is missing.

## A/B Decision

Baseline:

- `post_apply_evidence_gate.py` reported provider failures as counts:
  `provider_failed_checks`, `missing_cli`, and `auth_context_missing`.
- No-go promotion receipts listed generic post-apply failures but did not carry
  the exact provider command or remediation that blocked release.

Variant:

- Add a redacted `provider_blockers` array from
  `provider_preflight.failed_checks`.
- Add `provider_blocker_count` to the post-apply summary.
- Print provider blocker command, reason, docs URL, and remediation in the text
  report.
- Include provider blocker next actions in no-go promotion receipt
  `blocking_reasons`.

Decision rule:

- Adopt if post-apply tests stay green, generated no-go evidence remains
  fail-closed, and live Railway/Vercel blockers appear in post-apply JSON,
  console output, and promotion receipts without exposing secret-shaped values.

Result: adopted.

## Current Evidence

- `python scripts\post_apply_evidence_gate.py --external-gate-json var\external-release-gate-provider-remediation-2026-07-04.json --json-out var\post-apply-evidence-gate-provider-blockers-2026-07-04.json --manifest-out var\post-apply-evidence-manifest-provider-blockers-2026-07-04.json --verify-manifest-out var\post-apply-evidence-manifest-verify-provider-blockers-2026-07-04.json --promotion-receipt-out var\post-apply-promotion-receipt-provider-blockers-2026-07-04.json`
  - Expected exit code `1`.
  - `ok=false`, `failures=9`.
  - `provider_blockers=4`.
  - Railway blockers include `next=Run railway login...`.
  - Vercel blockers include `next=Set VERCEL_TOKEN or run vercel login...`.
- `python scripts\post_apply_evidence_gate.py --verify-promotion-receipt var\post-apply-promotion-receipt-provider-blockers-2026-07-04.json --json-out var\post-apply-promotion-receipt-verify-provider-blockers-2026-07-04.json`
  - Exit code `0`.
  - Receipt verification is valid for a no-go receipt:
    `ok=true`, `receipt_ok=false`, `decision=no-go`, `artifact_failures=0`,
    `secret_markers=0`.

## Verification

- `python -m py_compile scripts\post_apply_evidence_gate.py`
  - Exit code `0`.
- `python -m pytest backend\tests\test_post_apply_evidence_gate.py -q`
  - `27 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `87 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `133 passed`.

## Current Boundary

Launch remains externally blocked. The post-apply path now explains the
Railway/Vercel recovery actions, but the actual public release still requires an
operator to authenticate or relink provider CLIs, apply real provider secrets,
and rerun the release gates.

## Next Cycle

The next local cycle should inspect CI/workflow outputs and GitHub annotations
for any remaining no-go provider summaries that omit remediation context.
