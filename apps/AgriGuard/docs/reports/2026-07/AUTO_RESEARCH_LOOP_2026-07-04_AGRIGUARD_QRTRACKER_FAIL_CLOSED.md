# AutoResearch Loop - AgriGuard QRTracker Fail-Closed Guard

Date: 2026-07-04
App: AgriGuard
Cycle: QRTracker edge-state hardening

## Baseline

`QRTracker` built a fallback URL with `window.location.origin` and `productId`. If a caller rendered the component without both an explicit QR value and a product id, it could produce a QR for `/product/undefined`.

## Variant

Adopted a fail-closed component state:

- Explicit QR values still render a local QR code.
- Product ids still produce the existing `/product/{id}` fallback URL.
- Missing QR input now renders an accessible `Product verification QR unavailable` status instead of generating an invalid QR.
- Added a component test for both the explicit-value path and the missing-input path.

## Evidence

- `npm run test -- QRTracker.test.jsx`
  - Test files: 1 passed
  - Tests: 2 passed
- `npm run lint`
  - Status: pass
- `npm run build:lts`
  - Status: pass
- `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5197 --api-url http://127.0.0.1:8011 --operator-token browser-smoke-token --mobile --json-out var/agriguard-qrtracker-failclosed-browser-2026-07-04/product-detail-qrtracker-mobile.json --screenshot-dir var/agriguard-qrtracker-failclosed-browser-2026-07-04/product-detail-qrtracker-mobile-screens --timeout-ms 30000`
  - Status: pass
  - Checks: 19/19
  - `local_qr_code_visible`: true
  - `no_external_qr_requests`: true
  - `externalQrRequests`: []
  - Mobile viewport: 390x844

## Decision

Adopt the fail-closed QRTracker variant. It prevents an invalid verification QR from being minted by mistake and preserves the product-detail QR workflow in browser verification.
