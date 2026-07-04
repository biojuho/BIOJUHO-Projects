# AutoResearch Loop - DeSci Apply Plan Context Blockers - 2026-07-04

## Objective

Prevent provider apply plans from reporting provider values as ready to apply when provider CLI authentication or project-link context remains blocked.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_APPLY_PLAN_CONTEXT_BLOCKERS.md`

## Source Evidence

- Railway CLI project context depends on a linked Railway project, such as `railway link`, `.railway`, or project-scoped configuration.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
- Vercel CLI project context depends on linked project metadata such as `.vercel/project.json` or project and org identifiers.
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local provider preflight evidence now marks unresolved provider scoping as `project_context_missing` and carries provider preflight failures through the external gate handoff.

## Baseline

- Provider apply-plan readiness only checked whether provider env templates had values for every required key.
- A filled Railway or Vercel template could be treated as ready to apply even if the local CLI was not authenticated or was not linked to a provider project.
- The apply-plan verifier did not expose provider preflight blocker counts or project-context blocker counts.

## A/B Decision

- Baseline A: keep provider apply readiness tied only to filled template values.
  - Rejected because operators could proceed to provider env application without resolving Railway/Vercel CLI auth and project scope.
- Variant B: require both filled templates and zero provider preflight blockers before a provider is `ready_to_apply`.
  - Adopted because it preserves secret-safe template handling while making provider auth/linking blockers explicit and machine-verifiable.

## Implementation

- Added provider preflight failure counts to the provider rollup and provider template index.
- Added `template_ready`, `provider_preflight_blocker_count`, `project_context_missing_count`, `blocked_reasons`, and preflight command/remediation details to provider apply-plan entries.
- Added operator-level `provider_preflight_blocker_count` and `provider_project_context_missing_count`.
- Added a new `resolve_provider_preflight` operator stage for filled templates that are still blocked by provider CLI context.
- Updated provider apply-plan verification to check env counts, preflight counts, project-context counts, and operator summary consistency.
- Updated provider apply-plan Markdown and console verification output to show provider preflight and project-context blocker counts.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `52 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `107 passed`
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-project-context-chain-2026-07-04.json --json-out var\external-gate-handoff-apply-plan-context-2026-07-04.json --markdown-out var\external-gate-handoff-apply-plan-context-2026-07-04.md --provider-template-dir var\provider-templates-apply-plan-context-2026-07-04 --provider-template-index-out var\provider-template-index-apply-plan-context-2026-07-04.json --provider-apply-plan-out var\provider-apply-plan-context-2026-07-04.json --provider-apply-plan-markdown-out var\provider-apply-plan-context-2026-07-04.md`
  - Expected exit: `1`
  - Result: generated handoff, provider templates, provider template index, provider apply plan JSON, and provider apply plan Markdown while preserving release `no-go`.
- `python scripts\external_gate_handoff.py --verify-provider-apply-plan var\provider-apply-plan-context-2026-07-04.json --json-out var\provider-apply-plan-verify-context-2026-07-04.json`
  - Result: `provider_apply_plan_ok=True`, `ready_to_apply=False`, providers `0/4`, provider preflight blockers `4`, project context missing `3`, provider failures `0`, secret markers `0`.
- `python scripts\external_gate_handoff.py --verify-provider-apply-plan var\provider-apply-plan-context-2026-07-04.json --require-ready-to-apply --json-out var\provider-apply-plan-require-ready-context-2026-07-04.json`
  - Expected exit: `1`
  - Result: `provider_apply_plan_ok=False`, `ready_to_apply=False`, providers `0/4`, provider preflight blockers `4`, project context missing `3`, provider failures `4`, failures `1`, secret markers `0`.
- Generated apply plan operator status:
  - Stage: `fill_provider_templates`
  - Ready to apply: `false`
  - Provider preflight blockers: `4`
  - Provider project context missing: `3`
  - Private template values present: `false`
- Generated provider apply-plan details:
  - Polygon Amoy: blank keys `5`, preflight blockers `0`, project context missing `0`.
  - GitHub: blank keys `1`, preflight blockers `0`, project context missing `0`.
  - Railway: blank keys `17`, preflight blockers `2`, project context missing `1`, blocked by blank template values, provider preflight blockers, and provider project context.
  - Vercel: blank keys `4`, preflight blockers `2`, project context missing `2`, blocked by blank template values, provider preflight blockers, and provider project context.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-apply-plan-context-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The apply plan now fails closed on these provider-context blockers instead of treating filled env templates as sufficient.

## Next Cycle

Continue hardening the provider apply workflow by making the apply-results recorder and workflow verifier surface the same provider-context blockers when an operator attempts to advance from plan to execution.
