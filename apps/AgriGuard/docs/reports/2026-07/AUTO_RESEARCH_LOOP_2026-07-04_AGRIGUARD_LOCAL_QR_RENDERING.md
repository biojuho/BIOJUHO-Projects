# AutoResearch Loop - AgriGuard Local QR Rendering

Date: 2026-07-04
App: AgriGuard
Cycle: Product detail QR rendering dependency hardening

## Baseline

The product detail route rendered the product QR code through a remote image URL:

`https://api.qrserver.com/v1/create-qr-code/`

That made the product verification card depend on a third-party image service at view time and exposed the QR payload through the request URL.

## Variant

Adopted the existing in-repo `react-qr-code` dependency through `QRTracker`:

- `QRTracker` now accepts an explicit QR value.
- `QRTracker` exposes a stable accessible image label: `Product verification QR`.
- `ProductDetail` renders `product.qr_code` locally instead of using the remote QR image URL.
- The product-detail browser smoke now fails if `api.qrserver.com` is requested.

During browser verification, the first variant exposed a real integration defect: the default `react-qr-code` import rendered as an object under the current Vite setup. The adopted variant uses the named `QRCode` export and passed the browser gate.

## Evidence

- `python -m py_compile apps/AgriGuard/scripts/product_detail_browser_smoke.py`
- `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5196 --api-url http://127.0.0.1:8010 --operator-token browser-smoke-token --mobile --json-out var/agriguard-local-qr-browser-2026-07-04/product-detail-local-qr-mobile.json --screenshot-dir var/agriguard-local-qr-browser-2026-07-04/product-detail-local-qr-mobile-screens --timeout-ms 30000`
  - Status: pass
  - Checks: 19/19
  - `local_qr_code_visible`: true
  - `no_external_qr_requests`: true
  - `externalQrRequests`: []
  - Mobile viewport: 390x844
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-local-qr-rendering.json`
  - Status: complete
  - Passed: 5/5
  - Failed: 0
  - Covered: frontend lint, frontend build, contracts compile, contracts tests, backend tests

## Decision

Adopt the local QR rendering variant. It removes the third-party runtime QR dependency, preserves the product-detail workflow, and adds a regression guard for accidental reintroduction of the external QR service.
