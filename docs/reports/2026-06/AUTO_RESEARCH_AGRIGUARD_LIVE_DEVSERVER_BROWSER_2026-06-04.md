# AutoResearch AgriGuard Live Dev-Server Browser Pass - 2026-06-04

## Scope

- App: `apps/AgriGuard`
- Surface: live local dev-server browser path
- Baseline: the new dev-server status manifest could mark the AgriGuard API and frontend reachable, but a Playwright click pass on the manifest frontend port found CORS console errors from `/dashboard/summary`. A follow-up browser pass on the currently allowed `localhost:5173` origin removed the CORS errors but exposed Recharts zero-size chart warnings.
- Variant adopted: add the manifest frontend port `http://127.0.0.1:5174` to the backend source/default CORS contract and stabilize dashboard Recharts containers with explicit numeric heights plus minimum width.

## Changed Paths

- `apps/AgriGuard/backend/main.py`
- `apps/AgriGuard/backend/.env.example`
- `apps/AgriGuard/backend/tests/test_cors_origins.py`
- `apps/AgriGuard/frontend/src/components/dashboard/Dashboard.jsx`
- `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_LIVE_DEVSERVER_BROWSER_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- the backend source/default CORS contract includes the dev-server manifest frontend port,
- a focused backend test locks that origin into the default contract,
- the live browser pass can click Dashboard -> Registry -> Supply Chain with no console warnings/errors,
- the frontend production build succeeds,
- canonical AgriGuard smoke still passes.

## Evidence

- Initial manifest-port browser finding:
  - Frontend: `http://127.0.0.1:5174`
  - Evidence: `var/agriguard-live-devserver-browser-2026-06-04.json`
  - Result: navigation worked, but `/dashboard/summary` CORS failed because the live Docker/WSL backend process had not allowed `http://127.0.0.1:5174`.
- Current live-process browser pass:
  - Frontend: `http://localhost:5173`
  - Evidence: `var/agriguard-live-devserver-localhost-clean-browser-2026-06-04.json`
  - Screenshot: `var/agriguard-live-devserver-localhost-clean-supply-chain-2026-06-04.png`
  - Result: Dashboard -> Registry -> Supply Chain, `0` console warnings/errors, `0` page errors.
- Backend CORS contract:
  - `python -m pytest apps\AgriGuard\backend\tests\test_cors_origins.py -q -p no:cacheprovider`
  - Result: `1` passed, `1` expected insecure-local-secret warning.
- Frontend build:
  - `npm run build`
  - Result: passed, no chunk-size warning.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-live-devserver-cors-chart-2026-06-04.json`
  - Result: passed `5/5`.

## Remaining Launch Work

- Restart or refresh the live Docker/WSL AgriGuard backend environment before expecting `http://127.0.0.1:5174` to pass in the already-running process.
- Keep the dev-server manifest and backend `ALLOWED_ORIGINS` synchronized if future app ports are added.
