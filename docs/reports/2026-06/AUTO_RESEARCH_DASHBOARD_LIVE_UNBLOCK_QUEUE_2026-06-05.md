# Dashboard Live Unblock Queue

- Date: 2026-06-05
- Scope: dashboard credential-boundary operator surface
- Baseline: the Quality panel showed the next credential unblock but not the remaining live-verifier queue after Canva.
- Variant: expose a sanitized `live_plan` queue from the dry-run verifier and render the first two queue items as visible metric rows, with a supporting queue table.
- Primary KPI: improve operator planning for credential-gated launch blockers.
- Guardrails: no credential values; no new execution path; no claim that blocked external actions are complete; browser and workspace checks stay green.

## Adopted Variant

Adopted. The dashboard now exposes and renders the live unblock queue. The visible rows show `Queue #1` as `Canva OAuth and OpenAPI tool execution` and `Queue #2` as `GitHub source-refresh token boundary`, while the detail table keeps the live status list available.

An initial browser-smoke attempt failed because the lower queue table was not visible in the clipped Quality panel. The accepted variant moved the first two queue items into visible metric rows and re-ran browser smoke successfully.

## Changed Paths

- `apps/dashboard/routers/gdt.py`
- `apps/dashboard/src/components/QualityPanel.jsx`
- `apps/dashboard/src/App.test.jsx`
- `tests/test_dashboard_api.py`
- `ops/references/dev_server_browser_checks.json`

## Verification

- `python -m pytest tests\test_dashboard_api.py -q` -> `51 passed`
- `cmd /c "cd apps\dashboard && npm test -- --run"` -> `9 passed`
- `cmd /c "cd apps\dashboard && npm run build"` -> pass; existing Lightning CSS `@extend` warning remains
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-live-queue-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_LIVE_QUEUE_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_LIVE_QUEUE_2026-06-05.md` -> `1/1 routes`, `failed=0`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-live-queue-2026-06-05.json` -> `6/6 passed`
- Managed dashboard cleanup: final status `0/2 ready`

## Remaining Boundary

The live queue still reports credential-gated work. Canva remains blocked until the operator provides `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, and user login/consent. GitHub live refresh remains blocked without `GITHUB_TOKEN` or `GH_TOKEN`.

global_objective_complete=false
