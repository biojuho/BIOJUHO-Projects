# AutoResearch Loop - AgriGuard Frontend API Proxy Default

Date: 2026-07-04
App: AgriGuard
Cycle: Frontend API base URL launch hardening

## Baseline

The frontend API client defaulted to `http://127.0.0.1:8002` when `VITE_API_URL` was unset. That works on a developer machine, but it is unsafe for a launched browser build because `127.0.0.1` resolves to the user's device, not the deployed backend.

The app already has same-origin API proxying:

- Vite dev proxy: `/api` to `http://127.0.0.1:8002`
- Frontend nginx proxy: `/api/` to the backend service

## Variant

Adopted `/api` as the frontend API default:

- `resolveApiBaseUrl()` returns `VITE_API_URL.trim()` when explicitly configured.
- Without explicit config, the frontend uses `/api`.
- `frontend/.env.example` now documents `VITE_API_URL=/api`.
- Replaced the mojibake API service test with ASCII coverage for the `/api` default and product API error propagation.

## Evidence

- `npm run test -- api.test.js`
  - Test files: 1 passed
  - Tests: 4 passed
- `npm run lint`
  - Status: pass
- `npm run build:lts`
  - Status: pass
- Browser smoke with `VITE_API_URL` unset and Vite proxying `/api` to backend port `8002`:
  - Command: `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5198 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --mobile --json-out var/agriguard-api-proxy-browser-2026-07-04/product-detail-api-proxy-mobile.json --screenshot-dir var/agriguard-api-proxy-browser-2026-07-04/product-detail-api-proxy-mobile-screens --timeout-ms 30000`
  - Status: pass
  - Checks: 19/19
  - `product_detail_loaded`: true
  - `local_qr_code_visible`: true
  - `no_request_failures`: true
  - `no_console_errors`: true

## Decision

Adopt the `/api` default. It matches the app's dev and nginx proxy topology and prevents production browser builds from silently targeting localhost when `VITE_API_URL` is omitted.
