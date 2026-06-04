# AutoResearch DeSci Firebase and CORS Browser Fix - 2026-06-04

## Source-Backed Candidate

- Source: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
- Source pattern: browser automation should catch local dev-server runtime failures that unit tests miss.
- Local surface: `apps/desci-platform` public launch routes and manifest-backed `desci-frontend` target.

## A/B Contract

- Baseline: DeSci dev servers reached `2/2 READY`, but browser smoke failed all public routes because Firebase threw `auth/invalid-api-key`. After fixing that, `/explore` still failed because backend CORS did not allow `http://127.0.0.1:5175`.
- Variant: make Firebase initialization conditional on complete non-placeholder env and include manifest frontend origins in the backend development CORS contract.
- Primary KPI: DeSci browser smoke returns `7/7 OK`, and click proof covers home, explore search, and pricing with zero console/page/request failures.
- Guardrails: real login/signup still require valid Firebase config; the fallback only keeps public/local smoke routes renderable.
- Decision: adopted.

## Changes

- `apps/desci-platform/frontend/src/firebase.js`
  - Exports `isFirebaseConfigured`.
  - Initializes Firebase only when all required values exist and are not template placeholders.
  - Exports inert `auth` and `googleProvider=null` for local public-route smoke when Firebase is not configured.
- `apps/desci-platform/frontend/src/contexts/AuthContext.jsx`
  - Skips `onAuthStateChanged` when Firebase is not configured.
  - Returns explicit auth-not-configured errors for login/signup attempts in that state.
- `apps/desci-platform/frontend/src/firebase.test.js`
  - Covers missing and placeholder Firebase env fallback.
- `apps/desci-platform/backend/main.py`
  - Adds `localhost` and `127.0.0.1` origins for dev ports `5173`, `5174`, and `5175`.
- `apps/desci-platform/backend/tests/test_api_endpoints.py`
  - Locks CORS preflight for `http://127.0.0.1:5175`.
- `.env.example` files
  - Align default CORS and document Firebase fallback boundary.

## Verification

- `npm.cmd test -- src\firebase.test.js src\services\api.test.js` in `apps/desci-platform/frontend`
  - `8 passed`
- `npm.cmd run build` in `apps/desci-platform/frontend`
  - passed
- `npm.cmd run typecheck` in `apps/desci-platform/frontend`
  - passed
- `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py::test_cors_allows_manifest_frontend_origin -q -p no:cacheprovider`
  - `1 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py -q -p no:cacheprovider`
  - `21 passed`
- `npm.cmd test` in `apps/desci-platform/frontend`
  - `70 passed`
- Managed DeSci stack:
  - start: `dev server ready: desci-frontend`
  - status: `2/2 READY`
  - final stop status: `0/2 READY`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --timeout 30`
  - `7/7 OK`
- Chromium click proof:
  - home opened
  - explore clicked and search filled with `AI`
  - pricing clicked and verified
  - console errors: `0`
  - page errors: `0`
  - failed requests: `0`
  - screenshot: `var/desci-live-click-firebase-cors-fix-2026-06-04.png`
  - JSON evidence: `var/desci-live-click-firebase-cors-fix-2026-06-04.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-firebase-cors-fix-2026-06-04.json`
  - `7/7 PASS`
