# Auto Research Loop - AgriGuard Browser Launch Smoke - 2026-07-06

## Objective

Refresh product-level browser evidence for the guarded AgriGuard launch path after the latest preflight artifact hardening. The loop verifies the live backend contract, frontend proxy alignment, operator token recovery, core operator routes, public QR verification, and the simulated unavailable consumer path on both desktop and mobile viewports.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_LAUNCH_SMOKE_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Runtime

- Backend: `python -m uvicorn main:app --host 127.0.0.1 --port 8060`
- Frontend: `npm.cmd run dev -- --host 127.0.0.1 --port 5330`
- Backend database: `var/agriguard-browser-smoke-20260706-8060-5330.sqlite`
- Frontend proxy target: `http://127.0.0.1:8060`
- Operator smoke token: `AGRIGUARD_BROWSER_OPERATOR_TOKEN=browser-smoke-token`
- Frontend operator token env: unset for the runner contract check

## Verification

- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5330 --api-url http://127.0.0.1:8060 --output-dir var\agriguard-browser-smoke-suite-20260706-desktop --json-out var\agriguard-browser-smoke-suite-20260706-desktop.json --timeout-ms 45000 --include-unavailable-check`
  - Result: exit `0`
  - Browser steps: `7/7`
  - Checks: `186/186`
  - Screenshots: `19/19`
  - Prechecks: `3/3`
  - Prechecks passed: `frontend_operator_token_env`, `backend_contract`, `backend_proxy_alignment`
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5330 --api-url http://127.0.0.1:8060 --output-dir var\agriguard-browser-smoke-suite-20260706-mobile --json-out var\agriguard-browser-smoke-suite-20260706-mobile.json --timeout-ms 45000 --include-unavailable-check --mobile`
  - Result: exit `0`
  - Browser steps: `7/7`
  - Checks: `191/191`
  - Screenshots: `19/19`
  - Prechecks: `3/3`
  - Prechecks passed: `frontend_operator_token_env`, `backend_contract`, `backend_proxy_alignment`

## Visual Sampling

- Desktop dashboard screenshot sampled from `var\agriguard-browser-smoke-suite-20260706-desktop\nav-screens\dashboard.png`.
  - Result: dashboard content rendered, navigation fit the viewport, and KPI/status cards did not overlap.
- Mobile registry screenshot sampled from `var\agriguard-browser-smoke-suite-20260706-mobile\nav-screens\registry.png`.
  - Result: first viewport contained the registration form and the `Register Harvest` CTA without clipping.
- Mobile public QR verification screenshot sampled from `var\agriguard-browser-smoke-suite-20260706-mobile\qr-path-screens\manual-verify.png`.
  - Result: public QR evidence state rendered, operator-only fields stayed redacted, and the consumer-facing status cards fit the mobile viewport.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. The latest guarded launch preflight reports the missing checked path as `C:\secure\missing-firebase-service-account.json`.
