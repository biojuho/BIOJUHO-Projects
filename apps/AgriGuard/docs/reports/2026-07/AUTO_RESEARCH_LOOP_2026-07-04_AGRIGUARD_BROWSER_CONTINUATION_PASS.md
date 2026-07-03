# AgriGuard AutoResearch Loop - browser continuation pass

Date: 2026-07-04

## Scope

Ran real browser-click validation against the live AgriGuard frontend at `http://127.0.0.1:5174`.

The existing frontend proxy expected a backend on `127.0.0.1:8002`, so a temporary backend was started on port `8002` with a disposable SQLite database under `var/`, test-bypass auth enabled, MQTT/simulation disabled, and `PUBLIC_VERIFY_BASE_URL=http://127.0.0.1:5174`.

## Browser Evidence

- Pass: `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5174 --mobile --click-nav --operator-token browser-smoke-token --json-out var/agriguard-browser-continuation-nav-mobile.json --screenshot-dir var/agriguard-browser-continuation-nav-shots --timeout-ms 20000` (`47/47 PASS`)
- Pass: `python apps/AgriGuard/scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --mobile --operator-token browser-smoke-token --json-out var/agriguard-browser-continuation-supply-mobile.json --screenshot var/agriguard-browser-continuation-supply-mobile.png --timeout-ms 30000` (`20/20 PASS`)
- Pass: `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-browser-continuation-qr.json --screenshot-dir var/agriguard-browser-continuation-qr-shots --timeout-ms 30000` (`22/22 PASS`)
- Pass: `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-browser-continuation-admin.json --screenshot-dir var/agriguard-browser-continuation-admin-shots --timeout-ms 30000`
- Pass: `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-browser-continuation-product-detail.json --screenshot-dir var/agriguard-browser-continuation-product-shots --timeout-ms 30000`

## Observations

- Mobile nav visited 7 launch routes by clicking visible navigation links: dashboard, registry, supply chain, QR tokens, sensors, cold-chain, and scanner.
- Supply-chain mobile smoke used `/api/products/page` and did not fall back to unpaginated `/products`.
- QR smoke covered invalid manual entry recovery, successful manual verification, invalid public verification, and mobile overflow checks.
- Admin smoke covered fail-closed missing-token states, QR token loading/reissue, sensor registration, and MQTT provisioning artifact rendering.
- Product-detail smoke covered seeded detail rendering, local QR rendering, operator tracking event, certification save, history labels, and overflow checks.
- QR smoke recorded one `net::ERR_ABORTED` request for `/api/qr-events`, classified by the smoke as non-actionable; all actionable request, console, and page-error checks passed.
- The temporary backend listener on `8002` was stopped after the browser checks.
