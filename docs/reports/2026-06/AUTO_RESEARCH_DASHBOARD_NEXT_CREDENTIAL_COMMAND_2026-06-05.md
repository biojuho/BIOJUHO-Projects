# Dashboard Next Credential Command

- Date: 2026-06-05
- Scope: dashboard credential-boundary operator surface
- Baseline: the Quality panel showed `Next Unblock` and env names, but operators still had to open the live-verifier report to find the first safe verification command.
- Variant: render the live verifier `first_verification_command` as a compact `Next command` row in the Quality panel.
- Primary KPI: reduce operator handoff friction for the next credential unblock.
- Guardrails: display the command from the dry-run artifact only; no credential values; no claim that Canva OAuth is complete; API/UI/browser/workspace checks stay green.

## Adopted Variant

Adopted. The dashboard now shows the first safe verifier command for the next credential unblock: `cd mcp/canva-mcp && npm run doctor:canva`. The row is display-only and uses the existing sanitized API field.

## Changed Paths

- `apps/dashboard/src/components/QualityPanel.jsx`
- `apps/dashboard/src/App.test.jsx`
- `tests/test_dashboard_api.py`
- `ops/references/dev_server_browser_checks.json`

## Verification

- `python -m pytest tests\test_dashboard_api.py -q` -> `51 passed`
- `cmd /c "cd apps\dashboard && npm test -- --run"` -> `9 passed`
- `cmd /c "cd apps\dashboard && npm run build"` -> pass; existing Lightning CSS `@extend` warning remains
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-next-command-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_NEXT_COMMAND_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_NEXT_COMMAND_2026-06-05.md` -> `1/1 routes`, `failed=0`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-next-command-2026-06-05.json` -> `6/6 passed`
- Managed dashboard cleanup: final status `0/2 ready`

## Remaining Boundary

The next command is still credential-gated after the local doctor step. Live Canva OAuth and OpenAPI execution still require operator-provided `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, and real user login/consent before the command sequence can be claimed complete.

global_objective_complete=false
