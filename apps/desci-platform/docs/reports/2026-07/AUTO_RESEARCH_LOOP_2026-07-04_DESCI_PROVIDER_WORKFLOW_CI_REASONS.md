# AutoResearch Loop: Provider Workflow CI Reasons

Date: 2026-07-04

## Objective

Make provider apply workflow verification expose the no-go promotion receipt's
blocking reasons to Markdown, console output, GitHub annotations, and GitHub
output variables.

## Scope

Owned paths changed in this cycle:

- `scripts/external_gate_handoff.py`
- `scripts/post_apply_evidence_gate.py`
- `backend/tests/test_external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`

The change preserves fail-closed workflow behavior. It only lifts already
validated no-go receipt reasons into workflow-facing output surfaces.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern is bounded status propagation: CI should present the
operator-facing recovery reason, not just a generic failed workflow state.

## A/B Decision

Baseline:

- `verify_provider_apply_workflow` embedded promotion receipt verification but
  did not expose receipt `blocking_reasons` at the workflow level.
- GitHub annotations reported generic workflow failures first, so provider
  recovery actions could be missing from CI-visible errors.

Variant:

- Return `blocking_reasons` from promotion receipt verification.
- Add workflow-level `promotion_blocking_reasons` and
  `promotion_blocking_reason_count`.
- Render those reasons in workflow Markdown and console output.
- Prioritize actionable `next=` provider blockers in GitHub annotations.
- Add GitHub output variables for blocking reason count and multiline reasons.

Decision rule:

- Adopt if workflow tests stay green and live workflow verification shows the
  Railway/Vercel recovery instructions in console output, Markdown, and
  GitHub-style annotations while remaining no-go.

Result: adopted.

## Current Evidence

- `python scripts\external_gate_handoff.py --record-provider-apply-results-from-plan var\external-gate-handoff-provider-remediation-apply-plan-2026-07-04.json --json-out var\provider-apply-results-dry-run-provider-blockers-2026-07-04.json`
  - Expected exit code `1`.
  - Dry-run apply results: `command_count=29`, `failed_commands=29`.
- `python scripts\external_gate_handoff.py --verify-provider-apply-workflow var\external-gate-handoff-provider-remediation-apply-plan-2026-07-04.json --provider-apply-results var\provider-apply-results-dry-run-provider-blockers-2026-07-04.json --promotion-receipt var\post-apply-promotion-receipt-provider-blockers-2026-07-04.json --require-promotion-go --json-out var\provider-apply-workflow-verify-provider-blockers-2026-07-04.json --markdown-out var\provider-apply-workflow-verify-provider-blockers-2026-07-04.md --github-annotations`
  - Expected exit code `1`.
  - `provider_apply_workflow_ok=false`.
  - `promotion_blocking_reasons=16`.
  - GitHub-style annotations include:
    `next=Run railway login...` and
    `next=Set VERCEL_TOKEN or run vercel login...`.

## Verification

- `python -m py_compile scripts\external_gate_handoff.py scripts\post_apply_evidence_gate.py`
  - Exit code `0`.
- `python -m pytest backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `78 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `133 passed`.

## Current Boundary

Launch remains no-go. The workflow now exposes the same provider recovery
instructions in CI-facing output, but Railway/Vercel authentication and real
provider secrets still require external operator action.

## Next Cycle

The next local cycle should inspect the release gate verifier for any remaining
JSON evidence checks that require remediation fields but do not validate the new
provider-blocker surfaces.
