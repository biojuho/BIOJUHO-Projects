# AutoResearch Loop - AgriGuard Supply Chain Proxy Smoke

Date: 2026-07-04
App: AgriGuard
Cycle: Browser smoke proxy-path correctness

## Baseline

The supply-chain mobile browser smoke rendered the page correctly and captured successful bounded product-page responses:

- `http://127.0.0.1:5174/api/products/page?page=1&page_size=20`
- `http://127.0.0.1:5174/api/products/page?page=1&page_size=20&search=...`

The smoke still failed `products_page_endpoint_used` and `products_page_payloads_bounded` because it compared raw response paths only to `/products/page`.

Risk:

- The app's launch path defaults frontend API calls to the `/api` proxy.
- A correct proxied paginated API request could be reported as a smoke failure.

## Variant

Added `api_response_path()` to normalize frontend-proxy paths:

- `/api/products/page` is treated as `/products/page`
- `/api/products` is treated as `/products`
- Direct backend paths remain unchanged

Added unit coverage in `test_smoke.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-supply-chain-proxy-smoke"`
  - Result: pass
- `python apps/AgriGuard/scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --operator-token browser-smoke-token --mobile --json-out var/agriguard-browser-smoke-2026-07-04/supply-chain-mobile-after-proxy-fix.json --screenshot var/agriguard-browser-smoke-2026-07-04/supply-chain-mobile-after-proxy-fix.png --timeout-ms 30000`
  - Result: 20/20 pass

## Decision

Adopt the proxy-aware browser-smoke path normalization. The smoke now matches the launched frontend `/api` proxy contract while still failing if the UI falls back to the unpaginated products endpoint.
