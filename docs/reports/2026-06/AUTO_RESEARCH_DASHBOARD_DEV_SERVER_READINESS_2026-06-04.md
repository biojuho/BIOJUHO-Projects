# AutoResearch: Dashboard Dev-Server Readiness Surface

Date: 2026-06-04

## Source-backed prompt

The dashboard now shows workspace smoke timing evidence. The next adjacent
operator gap was live dev-server readiness: `dev_server_status.py` already
produces schema-v1 readiness artifacts, but dashboard users could not see which
local app targets were ready or degraded.

## A/B contract

- Baseline: the quality panel showed smoke timing, but no dev-server readiness
  status. Operators still had to open `var/dev-server-status*.json` manually.
- Variant: extend `/api/quality_overview` with a backward-compatible
  `dev_server_status` object and render ready counts plus target details in
  `QualityPanel`.
- KPI: a live dashboard stack can read the newest ready status artifact, show
  `2/2 READY`, survive an operator refresh, and finish with managed stop
  evidence.

## Adopted variant

The dashboard dev-server readiness surface was adopted.

Implementation:

- `apps/dashboard/routers/gdt.py` now reads the newest non-validated
  `var/dev-server-status*.json` artifact, normalizes summary/target fields, and
  exposes `dev_server_status`.
- `apps/dashboard/src/components/QualityPanel.jsx` now displays dev-server
  readiness counts and the monitored targets or unready targets.
- `tests/test_dashboard_api.py` and `apps/dashboard/src/App.test.jsx` cover the
  API payload and visible React panel.

## Verification

- `python -m py_compile apps\dashboard\routers\gdt.py` -> PASS
- `python -m pytest tests\test_dashboard_api.py -q -p no:cacheprovider` ->
  `49 passed`
- `npm ci` in `apps/dashboard` -> installed dependencies, `0` vulnerabilities
- `npm.cmd run test -- src/App.test.jsx` -> `5 passed`
- `npm.cmd run lint` -> PASS
- `npm.cmd run build` -> PASS; retained the pre-existing Lightning CSS
  `@extend` warning in `src/index.css`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-dashboard-devstatus-2026-06-04.json`
  -> `2/2 PASS`

Live dashboard proof:

- Baseline readiness:
  `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var\dev-server-status-dashboard-devstatus-before-2026-06-04.json`
  -> `0/2 ready`
- Start:
  `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-devstatus-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  -> `dashboard-frontend` ready, `attempts=1`, with dependency start
- Ready artifact:
  `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 2 --json-out var\dev-server-status-dashboard-devstatus-ready-2026-06-04.json`
  -> `2/2 ready`
- Browser opened `http://127.0.0.1:5173/`, loaded the dashboard, clicked the
  refresh button, and reported `0` console errors and `0` warnings.
- Live proxied API check at `/api/quality_overview` returned
  `dev_server_status.available=true`, `status=ready`, `ready=2/total=2`, and
  both `dashboard-api` and `dashboard-frontend` as OK.
- Stop:
  `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-devstatus-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 10`
  -> stopped the stack
- Final status:
  `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var\dev-server-status-dashboard-devstatus-after-stop-2026-06-04.json`
  -> `0/2 ready`

## Follow-up

The dashboard now has both deterministic smoke timing and live dev-server
readiness in one operator panel.
