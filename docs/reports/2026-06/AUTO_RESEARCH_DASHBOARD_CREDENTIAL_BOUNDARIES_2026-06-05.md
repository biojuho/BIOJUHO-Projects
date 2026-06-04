# AutoResearch: Dashboard Credential Boundaries

## Objective

Make credential-gated launch blockers visible in the operator dashboard, not
only in CLI output and repo reports.

## A/B Contract

- Baseline: credential blockers were machine-readable through
  `ops/references/external_credential_boundaries.json` and
  `EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json`, but the dashboard
  Quality panel did not expose them.
- Variant: add a read-only `credential_boundaries` block to
  `/api/quality_overview`, render a compact Credential Boundaries section in
  `QualityPanel`, and make the manifest-backed dashboard browser smoke require
  the rendered panel text.
- Primary KPI: live dashboard browser smoke passes with the Credential
  Boundaries panel visible.
- Guardrails: dashboard API tests, React tests, lint/build/bundle checks, direct
  refresh-click proof, and workspace smoke must remain green.

## Adopted Variant

Adopted.

- API: `apps/dashboard/routers/gdt.py`
- UI: `apps/dashboard/src/components/QualityPanel.jsx`
- UI fixture/test: `apps/dashboard/src/App.test.jsx`
- API regression test: `tests/test_dashboard_api.py`
- Browser route contract: `ops/references/dev_server_browser_checks.json`
- Browser smoke JSON:
  `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_CREDENTIAL_BOUNDARIES_2026-06-05.json`
- Browser smoke Markdown:
  `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_CREDENTIAL_BOUNDARIES_2026-06-05.md`
- Direct click proof JSON:
  `docs/reports/2026-06/DASHBOARD_CREDENTIAL_BOUNDARIES_CLICK_2026-06-05.json`
- Direct click proof Markdown:
  `docs/reports/2026-06/DASHBOARD_CREDENTIAL_BOUNDARIES_CLICK_2026-06-05.md`

## Verification

- `python -m pytest tests/test_dashboard_api.py tests/test_dev_server_browser_smoke.py -q --tb=line`
  - `55 passed`
- `npm test` in `apps/dashboard`
  - `9 passed`
- `npm run lint` in `apps/dashboard`
  - passed
- `npm run build` in `apps/dashboard`
  - passed
  - noted existing Lightning CSS warning for `.refresh-btn { @extend .btn; }`
- `npm run check:bundle` in `apps/dashboard`
  - passed
- Managed dashboard stack:
  - start reached `2/2 ready`
  - stop returned `0/2 ready`
- `python ops/scripts/dev_server_browser_smoke.py --target dashboard-frontend --timeout 30 ...`
  - `1/1` routes passed
  - required text included `CREDENTIAL BOUNDARIES` and
    `Canva OAuth and OpenAPI tool execution`
- Direct click proof:
  - loaded `http://127.0.0.1:5173/`
  - clicked refresh
  - verified `CREDENTIAL BOUNDARIES`, `5 ACTION`, and
    `Canva OAuth and OpenAPI tool execution`
  - console errors `0`
  - page errors `0`
  - request failures `0`
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-dashboard-credential-boundaries-2026-06-05.json`
  - `6/6 PASS`

## Remaining Boundary

This is operator visibility only. It does not satisfy external credentials:
Canva login/consent, OTLP endpoint credentials, hosted runtime credentials,
GitHub token-backed high-volume refreshes, and Telegram delivery credentials
remain explicit operator-owned blockers.
