# AutoResearch Loop: Provider Preflight Remediation

Date: 2026-07-04

## Objective

Improve the DeSci launch handoff for the current external provider blocker by
turning provider preflight failures into operator-ready next actions in console,
JSON, and release handoff Markdown.

## Scope

Owned paths changed in this cycle:

- `scripts/provider_preflight.py`
- `scripts/release_handoff.py`
- `backend/tests/test_provider_preflight.py`
- `backend/tests/test_deploy_readiness.py`

No frontend or app-click behavior changed in this cycle. Existing launch-click
coverage remains the user-facing evidence surface; this loop hardens the
provider-readiness handoff that follows it.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern is bounded: keep the continuous launch loop deterministic by
turning failed provider checks into durable, machine-readable status and explicit
next actions instead of relying on chat-only operator notes.

## A/B Decision

Baseline:

- Provider preflight and release handoff exposed provider, command,
  `failure_reason`, and docs URL.
- Railway and Vercel auth-context failures still required the operator to infer
  the next recovery step from raw error text or separate documentation.

Variant:

- Add a `remediation` field to failed provider checks.
- Preserve the field in the flattened `failed_checks` list.
- Render `next=...` in provider preflight console output and release handoff
  Markdown.

Decision rule:

- Adopt if the variant keeps all existing readiness contracts green, preserves
  failure classification counts, and makes current Railway/Vercel blockers
  actionable in generated evidence.

Result: adopted.

## Current Evidence

- `python scripts\provider_preflight.py --json-out var\provider-preflight-current-remediation-2026-07-04.json --include-output-preview`
  - Expected exit code `1`.
  - GitHub OK.
  - Railway failed `railway whoami` and `railway status` as
    `auth_context_missing`.
  - Vercel failed `vercel whoami` and `vercel env ls production` as
    `auth_context_missing`.
  - Failed checks now include `next=Run railway login...` or
    `next=Set VERCEL_TOKEN or run vercel login...`.
- `python scripts\release_handoff.py --product-smoke-json var\product-smoke-current-after-click-complete-2026-07-04.json --deploy-readiness-json var\deploy-readiness-production-example-cli-2026-07-04.json --provider-preflight-json var\provider-preflight-current-remediation-2026-07-04.json --json-out var\release-handoff-provider-remediation-2026-07-04.json --markdown-out var\release-handoff-provider-remediation-2026-07-04.md --env-template-out var\release-handoff-provider-remediation-2026-07-04.env --provider-template-dir var\release-handoff-provider-remediation-templates`
  - Expected exit code `1`.
  - Release decision remains `no-go`.
  - Provider CLI Preflight section includes remediation for Railway and Vercel.

## Verification

- `python -m py_compile scripts\provider_preflight.py scripts\release_handoff.py`
  - Exit code `0`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py -q`
  - `46 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py backend\tests\test_release_gate.py -q`
  - `161 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-provider-remediation-2026-07-04.json`
  - `8 passed, 0 failed`.

## Current Boundary

Local readiness automation is improved, but public launch remains externally
blocked until an operator authenticates/links Railway and Vercel, applies real
provider secrets and deployment values, then reruns provider preflight, deploy
readiness, release handoff, and product readiness.

## Next Cycle

The next highest-value local cycle is to propagate the same remediation field
through any remaining provider gate artifacts that still summarize only
`failure_reason`, so every no-go path presents the same recovery instruction.
