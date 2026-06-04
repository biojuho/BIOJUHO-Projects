# AutoResearch AgriGuard CORS and API Fallback Fix - 2026-06-04

## Scope

- App: `apps/AgriGuard`
- Baseline: `http://127.0.0.1:5173` browser paths could fail while `http://localhost:5173` worked. The frontend defaulted API calls to `http://localhost:8002`, but this Windows machine also has non-AgriGuard listeners on `localhost`/IPv6 port `8002`; preflight requests could miss the actual backend.
- Variant adopted: include `http://127.0.0.1:5173` in the backend default allowed origins and `.env.example`, and make the frontend development fallback target `http://127.0.0.1:8002`.

## Changed Paths

- `apps/AgriGuard/backend/main.py`
- `apps/AgriGuard/backend/.env.example`
- `apps/AgriGuard/frontend/.env.example`
- `apps/AgriGuard/frontend/src/services/api.js`
- `apps/AgriGuard/frontend/src/services/api.test.js`

## Decision Rule

Adopt the variant if:

- the backend responds to an OPTIONS preflight from `http://127.0.0.1:5173`,
- the scanner route no longer reports CORS/API console errors after the dev service-worker cache cleanup,
- the API client unit test still passes,
- the canonical AgriGuard smoke scope passes.

## Evidence

- Direct backend preflight:
  - `OPTIONS http://127.0.0.1:8002/qr-events`
  - Origin: `http://127.0.0.1:5173`
  - Result: `200`, `Access-Control-Allow-Origin=http://127.0.0.1:5173`
- Browser route:
  - `http://127.0.0.1:5173/scan?cors_fix=20260604b`
  - Snapshot: `agriguard-scan-cors-fixed.md`
  - Console: `agriguard-scan-cors-fixed-console.md`
  - Result: `0` errors, `0` warnings.
- Focused test:
  - `npm run test -- src/services/api.test.js`
  - Result: `1` file passed, `3` tests passed.
- Backend syntax:
  - `python -m py_compile apps\AgriGuard\backend\main.py`
  - Result: passed.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-cors-2026-06-04.json`
  - Result: passed `5/5`.

## Remaining Launch Work

- `/supply-chain` still needs pagination or virtualization for the 500+ product dataset.
- Vite build still reports deprecated `advancedChunks` and large chunk warnings.
