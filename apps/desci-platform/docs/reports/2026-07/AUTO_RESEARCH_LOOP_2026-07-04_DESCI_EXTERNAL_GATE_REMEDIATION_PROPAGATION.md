# AutoResearch Loop: External Gate Remediation Propagation

Date: 2026-07-04

## Objective

Keep the provider auth recovery instructions from `provider_preflight.py`
available in the downstream external gate handoff, so every no-go provider path
shows the same operator-ready next action.

## Scope

Owned paths changed in this cycle:

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

This loop does not change readiness decisions or provider command execution. It
only preserves existing failed-check remediation metadata through action
grouping, provider rollup, JSON output, and Markdown rendering.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern remains a bounded continuous loop with machine-readable
status, explicit actionability, and fail-closed no-go evidence for external
blockers.

## A/B Decision

Baseline:

- `external_gate_handoff.py` grouped provider-preflight failed checks by
  provider and retained commands, failure reasons, and docs URLs.
- The new `remediation` field was dropped before next-action JSON and Markdown.

Variant:

- Add grouped `remediations` to provider-preflight next actions.
- Preserve per-check `remediation` inside grouped `actions`.
- Roll `remediations` into provider rollup.
- Render `next=...` in the Provider Rollup and Next Actions sections.

Decision rule:

- Adopt if existing external gate tests stay green and live Railway/Vercel
  auth-context failures render remediation in both JSON and Markdown.

Result: adopted.

## Current Evidence

- `python scripts\external_release_gate.py --target all --env-file .env.production.example --ignore-process-env --check-cli --json-out var\external-release-gate-provider-remediation-2026-07-04.json`
  - Expected exit code `1`.
  - `deploy_failed=13`, `deploy_warnings=3`.
  - `provider_ready=1/3`, `provider_failed_checks=4`.
  - `missing_cli=0`, `auth_context_missing=4`.
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-provider-remediation-2026-07-04.json --json-out var\external-gate-handoff-provider-remediation-2026-07-04.json --markdown-out var\external-gate-handoff-provider-remediation-2026-07-04.md --provider-template-dir var\external-gate-handoff-provider-remediation-templates --provider-template-index-out var\external-gate-handoff-provider-remediation-template-index-2026-07-04.json --provider-apply-plan-out var\external-gate-handoff-provider-remediation-apply-plan-2026-07-04.json --provider-apply-plan-markdown-out var\external-gate-handoff-provider-remediation-apply-plan-2026-07-04.md`
  - Expected exit code `1`.
  - `decision=no-go`, `next_actions=12`.
  - Markdown Provider Rollup and Next Actions now include:
    `next=Run railway login...` for Railway and
    `next=Set VERCEL_TOKEN or run vercel login...` for Vercel.
  - JSON includes `remediations` on provider-preflight next actions and provider
    rollups.

## Verification

- `python -m py_compile scripts\external_gate_handoff.py`
  - Exit code `0`.
- `python -m pytest backend\tests\test_external_gate_handoff.py -q`
  - `51 passed`.
- `python -m pytest backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `87 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `133 passed`.

## Current Boundary

Launch remains externally blocked. The local gate chain now gives consistent
operator recovery instructions, but Railway/Vercel auth context and real
provider secrets still must be applied outside this local workspace before a
public release can be marked go.

## Next Cycle

The next local cycle should inspect post-apply verifier and promotion artifacts
for any remaining places that summarize provider state without remediation or
operator action context.
