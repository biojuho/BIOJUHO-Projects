# AutoResearch Loop - DeSci Vercel Project Context - 2026-07-04

## Objective

Distinguish Vercel authentication blockers from Vercel project-link blockers in the DeSci provider preflight.

## Scope and Owned Paths

- `apps/desci-platform/scripts/provider_preflight.py`
- `apps/desci-platform/backend/tests/test_provider_preflight.py`

## Source Evidence

- Vercel CLI project linking docs state that `.vercel/project.json` contains the Vercel `orgId` and `projectId`.
  - https://vercel.com/docs/cli/project-linking
- Vercel CLI docs recommend `VERCEL_TOKEN` for CI/non-interactive authentication.
  - https://vercel.com/docs/cli
- Vercel CLI skill guidance used for deterministic linking:
  - `vercel link --yes --project <name-or-id> --scope <team>`
- Vercel environment-variable skill guidance used for CI context:
  - `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
- Veritas AutoResearch source observed with `git ls-remote`:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Baseline

- The provider preflight classified Vercel failures as `auth_context_missing`.
- The checkout had no `apps/desci-platform/.vercel/project.json`.
- Operators could not tell from the preflight summary whether `vercel link` or `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID` were also required.

## A/B Decision

- Baseline A: keep a single Vercel `auth_context_missing` blocker.
  - Rejected because it hides the project-link requirement when `vercel env ls production` cannot be safely scoped.
- Variant B: keep the compatible `auth_context_missing` failure reason, and add a separate `project_context_missing` flag/count.
  - Adopted because downstream gates keep their current auth blocker semantics while operators get a precise project-link action.

## Implementation

- Added Vercel project-context detection from:
  - `VERCEL_ORG_ID` plus `VERCEL_PROJECT_ID`
  - `.vercel/project.json` with `orgId` and `projectId`
- Added `project_context_missing` to failed checks when a Vercel check lacks project context.
- Added `summary.project_context_missing_count`.
- Extended Markdown output to show:
  - `Project context missing`
  - `project_context=missing` beside affected failed checks
- Extended Vercel remediation to include:
  - `vercel link --yes --project <name-or-id> --scope <team>`
  - or `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`

## Verification

- `python -m py_compile apps\desci-platform\scripts\provider_preflight.py`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py -q`
  - Result: `15 passed in 0.32s`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py -q`
  - Result: `24 passed in 0.48s`
- `python scripts\provider_preflight.py --json-out var\provider-preflight-vercel-project-context-2026-07-04.json --markdown-out var\provider-preflight-vercel-project-context-2026-07-04.md --include-output-preview`
  - Expected exit: `1`
  - Result: `ok=False`, providers ready `1/3`, failed checks `4`, missing CLI `0`, auth context missing `4`, project context missing `2`
  - Vercel failed checks now include `project_context_missing=True`
- Secret-shaped scan over changed source and generated provider artifacts: clean.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-vercel-project-context-2026-07-04.json`
  - Result: `passed=8, failed=0, total=8`

## Current Launch Boundary

Public launch remains blocked by external provider setup:

- Railway auth context missing.
- Vercel auth context missing.
- Vercel project context missing for this checkout.
- GitHub provider preflight is currently OK.

## Next Cycle

Once a Vercel project name/team or `.vercel/project.json` is available, rerun the preflight to confirm `project_context_missing_count=0`, then continue to the external release gate and post-apply evidence promotion.
