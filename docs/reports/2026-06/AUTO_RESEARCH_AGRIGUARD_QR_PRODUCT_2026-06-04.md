# AutoResearch AgriGuard QR/Product Verification - 2026-06-04

## Outcome

AgriGuard's QR verification path now has a clean launch browser proof. The `/scan` page emits a single `scan_start` event for the generated QR session, the product deep link emits `verification_complete`, and the public product page keeps protected operator mutations locked unless an explicit operator bearer token is available.

## Adopted Changes

- Added `getOperatorToken`, `hasOperatorToken`, and protected request config in `apps/AgriGuard/frontend/src/services/api.js`.
- Updated `ProductDetail` so public QR visitors see a read-only verification page instead of active mutation forms that can generate raw 401 console errors.
- Preserved operator updates when `VITE_AGRIGUARD_OPERATOR_TOKEN` or `localStorage.agriguard-operator-token` is present.
- Made `QRReader` idempotent for `scan_start` tracking per scan attempt, including dev StrictMode effect replay.
- Added focused tests for locked public product actions, protected 401 UI handling, and QR StrictMode scan-start deduplication.

## Browser Evidence

- URL path tested: `http://127.0.0.1:5174/scan` to `http://127.0.0.1:5174/product/dbb58381-d19a-49dd-8b9f-c4ae47107c2a?scan_source=qr_reader&scan_session=...&scan_variant=qr_page_v1`
- Product: `Organic Apple` (`dbb58381-d19a-49dd-8b9f-c4ae47107c2a`)
- QR session: `qr-1780566541244-zaps2d0g`
- Captured events: `scan_start`, `verification_complete`
- Protected operator actions locked: `true`
- Console warnings/errors: `0`
- Page errors: `0`
- App/API request failures: `0`
- External QR image failures: `0`
- Evidence log: `docs/reports/2026-06/agriguard-qr-product-console.md`
- Screenshot: `docs/reports/2026-06/agriguard-qr-product-clicks.png`

## Verification

- `npm.cmd run test -- src/components/ProductDetail.test.jsx src/services/api.test.js` -> `2 passed`, `9 passed`
- `npm.cmd run test -- src/components/ProductDetail.test.jsx src/components/QRReader.test.jsx src/services/api.test.js` -> `3 passed`, `14 passed`
- `python -m pytest apps\AgriGuard\backend\tests\test_product_and_qr_routes.py -q -p no:cacheprovider` -> `12 passed`
- `npm.cmd run build:dry` in `apps/AgriGuard/frontend` -> PASS
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-product-2026-06-04.json` -> `5/5 PASS`

## Remaining Boundary

This cycle did not add a full operator login flow. Mutating product chain state still correctly requires backend authentication; the product page now prevents unauthenticated public QR visitors from triggering those protected routes.
