# AutoResearch Loop - DeSci Gate Project Context Propagation - 2026-07-04

## Objective

Propagate provider project-context blockers from `provider_preflight.py` through the external release gate, handoff, post-apply gate, and promotion receipt.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_release_gate.py`
- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/scripts/post_apply_evidence_gate.py`
- `apps/desci-platform/backend/tests/test_external_release_gate.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_post_apply_evidence_gate.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_GATE_PROJECT_CONTEXT_PROPAGATION.md`

## Source Evidence

- Prior cycle source basis: Railway CLI project context comes from `railway link`, `.railway`, or a project-scoped `RAILWAY_TOKEN`.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Prior cycle source basis: Vercel project context comes from `.vercel/project.json` or `VERCEL_ORG_ID` plus `VERCEL_PROJECT_ID`.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local gate-chain source: `provider_preflight.py` now emits `summary.project_context_missing_count` and failed-check `project_context_missing`.

## Baseline

- `provider_preflight.py` emitted project-context facts.
- `external_release_gate.py` summarized missing CLI and auth counts but did not expose `provider_project_context_missing_count`.
- `external_gate_handoff.py` did not carry project-context counts into handoff summaries, provider rollups, Markdown, or console output.
- `post_apply_evidence_gate.py` did not require the project-context count to be zero before promotion, and provider blockers did not label `project_context=missing`.

## A/B Decision

- Baseline A: leave project-context details only in raw provider preflight JSON.
  - Rejected because downstream release artifacts could hide a provider scoping blocker from operators and promotion receipts.
- Variant B: propagate `provider_project_context_missing_count` through each gate summary, add provider-level project-context counts to handoff rollups, and fail post-apply promotion when the count is nonzero.
  - Adopted because it preserves existing auth/missing-CLI semantics while making project-link blockers durable across the release chain.

## Implementation

- Added `summary.provider_project_context_missing_count` to `external_release_gate.py`.
- Added console reporting for `project_context_missing` in external release gate output.
- Added project-context counts to external handoff summaries, Markdown, console output, next actions, and provider rollup.
- Added `project_context_missing` to post-apply provider blockers.
- Added post-apply validation failure: `summary.provider_project_context_missing_count must be 0`.
- Added `project_context=missing` to promotion blocking reasons and post-apply console blocker lines.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_release_gate.py apps\desci-platform\scripts\external_gate_handoff.py apps\desci-platform\scripts\post_apply_evidence_gate.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `88 passed in 6.27s`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `106 passed in 5.00s`
- `python scripts\external_release_gate.py --target all --json-out var\external-release-gate-project-context-chain-2026-07-04.json`
  - Expected exit: `1`
  - Result: `ok=False`, provider ready `1/3`, provider failed checks `4`, missing CLI `0`, auth context missing `4`, project context missing `3`
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-project-context-chain-2026-07-04.json --json-out var\external-gate-handoff-project-context-chain-2026-07-04.json --markdown-out var\external-gate-handoff-project-context-chain-2026-07-04.md`
  - Expected exit: `1`
  - Result: `release_decision=no-go`, next actions `12`, project context missing `3`
- `python scripts\post_apply_evidence_gate.py --external-gate-json var\external-release-gate-project-context-chain-2026-07-04.json --json-out var\post-apply-evidence-gate-project-context-chain-2026-07-04.json --manifest-out var\post-apply-evidence-manifest-project-context-chain-2026-07-04.json --verify-manifest-out var\post-apply-evidence-manifest-verify-project-context-chain-2026-07-04.json --promotion-receipt-out var\post-apply-promotion-receipt-project-context-chain-2026-07-04.json`
  - Expected exit: `1`
  - Result: `ok=False`, failure count `10`, provider blockers `4`, project context missing `3`
  - Promotion receipt includes `project_context=missing` blocking reasons for Railway `railway status` and both Vercel checks.
- First `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-project-context-chain-2026-07-04.json`
  - Result: `passed=7`, `failed=1`, `total=8`; transient failure was `desci contracts tests`.
- Direct rerun of the failed command:
  - `npm.cmd run test` in `apps/desci-platform/contracts`
  - Result: runtime config tests passed, Solidity/Mocha tests `77 passing`.
- Final aggregate rerun:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-project-context-chain-rerun-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context missing.
- Railway project context missing for `railway status`.
- Vercel auth context missing.
- Vercel project context missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The gate chain now preserves these blockers consistently; it does not recast the release as launch-ready.

## Next Cycle

Use the propagated blocker facts to refresh the operator handoff around provider apply plans, so Railway/Vercel linking prerequisites are visible before anyone fills provider env templates.
