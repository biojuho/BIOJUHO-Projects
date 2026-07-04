# AutoResearch Loop - DeSci Railway Project Context - 2026-07-04

## Objective

Expose missing Railway project-link context in the DeSci provider preflight without weakening the existing fail-closed provider gate.

## Scope and Owned Paths

- `apps/desci-platform/scripts/provider_preflight.py`
- `apps/desci-platform/backend/tests/test_provider_preflight.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_RAILWAY_PROJECT_CONTEXT.md`

## Source Evidence

- Railway CLI docs state `RAILWAY_TOKEN` is the project-token environment variable for project-level actions, and `RAILWAY_API_TOKEN` is for account/workspace-level actions.
  - https://docs.railway.com/cli
- Railway `link` docs state that linking stores project configuration in a `.railway` directory and includes project ID, environment ID, and optional service ID.
  - https://docs.railway.com/cli/link
- Railway `status` docs state that `railway status` displays the linked project, environment, and resources.
  - https://docs.railway.com/cli/status
- Railway `variable` docs state that environment variables are managed through `railway variable`, with service and environment targeting options.
  - https://docs.railway.com/cli/variable
- Local CLI evidence:
  - `railway --version`: `railway 5.15.0`
  - `railway status --json`: `Unauthorized. Please login with \`railway login\``
  - `apps/desci-platform/.railway`: absent

## Baseline

- Railway CLI was installed, but the app checkout had no `.railway` link directory.
- No `RAILWAY_*` environment variables were present.
- `railway status --json` failed as an authentication problem, so the provider preflight did not also surface that a linked Railway project/environment context was missing.
- Operators had to infer whether `railway link` or a project-scoped token was also required.

## A/B Decision

- Baseline A: keep Railway status failures classified only through CLI exit output.
  - Rejected because it hides a required operator setup step when the checkout is not linked.
- Variant B: preflight Railway commands that require a linked project, add `project_context_missing=True` when `.railway` or project-scoped token context is absent, and preserve `auth_context_missing` as the primary failure reason when auth is also absent.
  - Adopted because downstream gates keep compatible auth blocker semantics while the operator status now includes the missing Railway project-link action.

## Implementation

- Added Railway auth-context detection from:
  - `RAILWAY_TOKEN`
  - `RAILWAY_API_TOKEN`
  - likely Railway home auth/config files without reading or printing token values
- Added Railway project-context detection from:
  - `RAILWAY_TOKEN`
  - `RAILWAY_PROJECT_ID` plus `RAILWAY_ENVIRONMENT_ID`
  - a documented `.railway` link directory containing project and environment IDs
- Added Railway project-context preflight for commands that require a linked project, such as `railway status` and `railway variable list`.
- Kept help/version commands, explicit `--project` commands, and `railway whoami` outside project-context checks.
- Added Railway-specific remediation:
  - `railway link --project <id> --environment <name-or-id> --service <name-or-id>`
  - or `RAILWAY_TOKEN` for project-scoped automation

## Verification

- `python -m py_compile apps\desci-platform\scripts\provider_preflight.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py -q`
  - Result: `18 passed in 0.41s`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py -q`
  - Result: `27 passed in 0.43s`
- `python scripts\provider_preflight.py --json-out var\provider-preflight-railway-project-context-2026-07-04.json --markdown-out var\provider-preflight-railway-project-context-2026-07-04.md --include-output-preview`
  - Expected exit: `1`
  - Result: `ok=False`, providers ready `1/3`, checks passed `3/7`, failed checks `4`, missing CLI `0`, auth context missing `4`, project context missing `3`
  - Railway `railway status` now includes `project_context_missing=True` while preserving `failure_reason=auth_context_missing`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-railway-project-context-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out apps\desci-platform\var\browser-smoke-launch-click-railway-project-context-2026-07-04.json --screenshot-dir apps\desci-platform\var\browser-smoke-launch-click-railway-project-context-2026-07-04-screens --trace-on-failure-dir apps\desci-platform\var\browser-smoke-launch-click-railway-project-context-2026-07-04-traces`
  - Result: `passed=44`, `failed=0`, `total=44`

## Current Launch Boundary

Public launch remains externally blocked:

- Railway auth context missing.
- Railway project context missing for `railway status`.
- Vercel auth context missing.
- Vercel project context missing.
- GitHub provider preflight is currently OK.

This cycle improves operator precision only. It does not recast the release as launch-ready.

## Next Cycle

After Railway login/linking or a project-scoped `RAILWAY_TOKEN` is available, rerun provider preflight and the external release gate to confirm `project_context_missing_count` drops and the Railway provider can safely accept backend variables.
