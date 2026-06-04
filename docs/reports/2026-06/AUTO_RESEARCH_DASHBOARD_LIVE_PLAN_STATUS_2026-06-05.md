# Dashboard Live Plan Status

- Date: 2026-06-05
- Scope: dashboard credential-boundary operator surface
- Baseline: the Quality panel showed the next unblock, env names, and first command, but not the live verifier's plan rank, command count, or current live block state.
- Variant: render a compact `Live plan` row from the existing sanitized `next_unblock` fields.
- Primary KPI: improve operator clarity before attempting the next credential unblock.
- Guardrails: no credential values; no new execution path; no claim that Canva OAuth/OpenAPI execution is complete; browser and workspace checks stay green.

## Adopted Variant

Adopted. The dashboard now shows `Live plan` with `Rank 1 / 2 commands / blocked missing required env`, making it clear that Canva is first in the unblock queue, two verifier commands are planned, and the current blocker is missing required env.

## Changed Paths

- `apps/dashboard/src/components/QualityPanel.jsx`
- `apps/dashboard/src/App.test.jsx`
- `tests/test_dashboard_api.py`
- `ops/references/dev_server_browser_checks.json`

## Verification

- `python -m pytest tests\test_dashboard_api.py -q` -> `51 passed`
- `cmd /c "cd apps\dashboard && npm test -- --run"` -> `9 passed`
- `cmd /c "cd apps\dashboard && npm run build"` -> pass; existing Lightning CSS `@extend` warning remains
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-live-plan-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_LIVE_PLAN_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_LIVE_PLAN_2026-06-05.md` -> `1/1 routes`, `failed=0`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-live-plan-2026-06-05.json` -> `6/6 passed`
- Managed dashboard cleanup: final status `0/2 ready`

## Remaining Boundary

The live plan still reports `blocked missing required env`. Real Canva OAuth/OpenAPI execution remains blocked until the operator provides `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, and user login/consent.

global_objective_complete=false
