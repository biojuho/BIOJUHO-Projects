# Dashboard Next Credential Unblock

- Date: 2026-06-05
- Scope: dashboard credential-boundary operator surface
- Baseline: `/api/quality_overview` exposed the credential boundary audit table, but the dashboard did not surface the live verifier `next_unblock` target.
- Variant: add a sanitized `credential_boundaries.next_unblock` API field from the latest `EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN` artifact and render the next boundary plus env names in the Quality panel.
- Primary KPI: operator actionability for the next credential unblock.
- Guardrails: no credential values emitted; env names only; no credential completion claim; dashboard API, frontend, browser smoke, and workspace smoke stay green.

## Adopted Variant

Adopted. The dashboard now shows `Next Unblock` with `Canva OAuth and OpenAPI tool execution` and the env-name list `CANVA_CLIENT_ID, CANVA_CLIENT_SECRET`. The API copies only boundary identifiers, title, live status, plan rank, env names, command count, and report path from the dry-run artifact.

## Changed Paths

- `apps/dashboard/routers/gdt.py`
- `apps/dashboard/src/components/QualityPanel.jsx`
- `tests/test_dashboard_api.py`
- `apps/dashboard/src/App.test.jsx`
- `ops/references/dev_server_browser_checks.json`

## Verification

- `python -m pytest tests\test_dashboard_api.py -q` -> `51 passed`
- `cmd /c "cd apps\dashboard && npm test -- --run"` -> `9 passed`
- `cmd /c "cd apps\dashboard && npm run build"` -> pass; existing Lightning CSS `@extend` warning remains
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-next-unblock-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_NEXT_UNBLOCK_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_NEXT_UNBLOCK_2026-06-05.md` -> `1/1 routes`, `failed=0`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-next-unblock-2026-06-05.json` -> `6/6 passed`
- Managed dashboard cleanup: final status `0/2 ready`

## Remaining Boundary

The next unblock is still credential-gated: Canva OAuth and OpenAPI tool execution require real operator-provided `CANVA_CLIENT_ID` and `CANVA_CLIENT_SECRET`, then the live verification commands can run. This cycle improves visibility and actionability only; it does not claim the external credential boundary complete.

global_objective_complete=false
