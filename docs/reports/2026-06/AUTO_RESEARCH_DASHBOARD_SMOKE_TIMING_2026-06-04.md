# AutoResearch: Dashboard Smoke Timing Surface

Date: 2026-06-04

## Source-backed prompt

The prior smoke-metrics cycle made `run_workspace_smoke.py --json-out` emit
schema-v1 timing evidence. The remaining operator gap was visibility: dashboard
users still had no way to see the latest smoke gate status or identify the
slowest checks without opening raw JSON.

## A/B contract

- Baseline: `/api/quality_overview` returned QA/content production metrics, but
  no workspace smoke timing summary. The browser shell also emitted a favicon
  404 during live dashboard QA.
- Variant: extend `/api/quality_overview` with a backward-compatible
  `workspace_smoke` object, render the latest gate status and slowest checks in
  `QualityPanel`, and add a static dashboard favicon so browser console evidence
  stays clean.
- KPI: the dashboard shows the latest smoke pass/fail status and top slow check
  after an operator refresh, while existing quality endpoint keys remain present.

## Adopted variant

The dashboard smoke timing surface was adopted.

Implementation:

- `apps/dashboard/routers/gdt.py` now reads the newest smoke report from
  `var/smoke/*.json` or `var/workspace-smoke*.json`, normalizes legacy array and
  schema-v1 envelope formats, and returns `workspace_smoke`.
- `apps/dashboard/src/components/QualityPanel.jsx` now displays latest smoke
  status, run duration, and the top three slowest checks.
- `apps/dashboard/index.html` and `apps/dashboard/public/favicon.svg` remove the
  dashboard favicon 404 seen during browser QA.
- `tests/test_dashboard_api.py` and `apps/dashboard/src/App.test.jsx` cover the
  API parser and visible React panel.

## Verification

- `python -m py_compile apps\dashboard\routers\gdt.py` -> PASS
- `python -m pytest tests\test_dashboard_api.py -q -p no:cacheprovider` ->
  `48 passed`
- `npm ci` in `apps/dashboard` -> installed dependencies, `0` vulnerabilities
- `npm.cmd run test -- src/App.test.jsx` -> `4 passed`
- `npm.cmd run lint` -> PASS
- `npm.cmd run build` -> PASS; retained the pre-existing Lightning CSS
  `@extend` warning in `src/index.css`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-dashboard-metrics-2026-06-04.json`
  -> `2/2 PASS`

Live dashboard proof:

- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-smoke-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  -> `dashboard-frontend` ready, `attempts=1`, with `dashboard-api` dependency
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 2 --json-out var\dev-server-status-dashboard-smoke-ready-2026-06-04.json`
  -> `2/2 ready`
- Browser opened `http://127.0.0.1:5173/`, loaded the dashboard, clicked the
  refresh button, and reported `0` console errors and `0` warnings after the
  favicon fix.
- Live proxied API check at `/api/quality_overview` returned
  `workspace_smoke.available=true`, `status=complete`, `passed=2/total=2`, and
  `cie tests` as the slowest check.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-smoke-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 10`
  -> stopped the stack
- Final status:
  `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var\dev-server-status-dashboard-smoke-after-stop-2026-06-04.json`
  -> `0/2 ready`

## Follow-up

The dashboard now consumes smoke timing evidence. A later dashboard pass can
fold dev-server readiness artifacts into the same operator panel.
