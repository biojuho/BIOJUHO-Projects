# AutoResearch Dashboard Generic Browser Smoke - 2026-06-04

## Objective

Use the new manifest-backed browser smoke runner on the workspace dashboard
operator surface and preserve launch evidence for the dashboard target.

## A/B Contract

- Baseline: dashboard browser evidence existed in earlier per-cycle reports, but
  the new generic `dev_server_browser_smoke.py` runner had only been live-proven
  against DeSci.
- Variant: run the same manifest-backed browser smoke against
  `dashboard-frontend` through the managed dev-server stack.
- Primary KPI: `dashboard-frontend` passes its configured browser route with no
  console/page/request failures.
- Guardrails: managed stack is stopped after proof, dev-server control/status
  tests remain green, and completion audit remains valid.

## Verification

- `python ops\scripts\dev_server_browser_smoke.py --validate-only --target dashboard-frontend --json-out var\dev-server-browser-smoke-dashboard-validate-2026-06-04.json`
  - Result: valid, `1` configured route.
- First managed start:
  `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-generic-browser-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  - Result: frontend started unready because local `apps/dashboard/node_modules`
    was missing Vite.
- `npm ci` in `apps/dashboard`
  - Result: `347 packages` installed locally, `0 vulnerabilities`.
- Ready managed start:
  `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-generic-browser-start-ready-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  - Result: ready, dashboard frontend pid `23180`, attempts `2`.
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_2026-06-04.md`
  - Result: pass, `1/1` route, no failures.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-generic-browser-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 10`
  - Result: stopped.
- `python -m pytest tests\test_dev_server_browser_smoke.py tests\test_dev_server_control.py tests\test_dev_server_status.py`
  - Result: `25 passed`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-dashboard-browser-smoke-2026-06-04.json`
  - Result: valid, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.

## Decision

Adopted. The dashboard operator surface now has committed generic browser-smoke
evidence under the same manifest-backed runner used for DeSci.
