# AutoResearch Loop - AgriGuard Current Browser Pass

Date: 2026-07-04
App: AgriGuard
Cycle: Current browser click-through verification

## Runtime

Frontend:

- Reused existing Vite dev server on `http://127.0.0.1:5174`.

Backend:

- Started a temporary local backend on `http://127.0.0.1:8002`.
- Used SQLite under `var/`.
- Set `AUTO_CREATE_SCHEMA=true`, `ALLOW_TEST_BYPASS=true`, `ALLOW_DEV_AUTH_FALLBACK=true`, `DEV_AUTH_FALLBACK_ROLE=operator`, `IOT_MQTT_ENABLED=false`, and `IOT_SIMULATION_ENABLED=false`.
- Stopped the temporary backend after the browser checks.

## Evidence

- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token browser-smoke-token --mobile --click-nav --json-out var/agriguard-browser-smoke-2026-07-04/nav-click-mobile.json --screenshot-dir var/agriguard-browser-smoke-2026-07-04/nav-click-mobile-screens --timeout-ms 30000`
  - Result: 47/47 pass
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-browser-smoke-2026-07-04/admin-routes.json --screenshot-dir var/agriguard-browser-smoke-2026-07-04/admin-routes-screens --timeout-ms 30000`
  - Result: pass
- `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --mobile --json-out var/agriguard-browser-smoke-2026-07-04/product-detail-mobile.json --screenshot-dir var/agriguard-browser-smoke-2026-07-04/product-detail-mobile-screens --timeout-ms 30000`
  - Result: pass
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-browser-smoke-2026-07-04/qr-path.json --screenshot-dir var/agriguard-browser-smoke-2026-07-04/qr-path-screens --timeout-ms 30000`
  - Result: 22/22 pass
- `python apps/AgriGuard/scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --operator-token browser-smoke-token --mobile --json-out var/agriguard-browser-smoke-2026-07-04/supply-chain-mobile-after-proxy-fix.json --screenshot var/agriguard-browser-smoke-2026-07-04/supply-chain-mobile-after-proxy-fix.png --timeout-ms 30000`
  - Result: 20/20 pass

## Decision

Use this as the current browser-level launch evidence after the compose/nginx hardening and supply-chain smoke proxy fix. The verified surfaces cover mobile navigation, admin QR/sensor routes, mobile product detail, public QR verification, and mobile supply-chain list/search/pagination behavior.
