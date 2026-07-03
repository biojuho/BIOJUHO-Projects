# AutoResearch Loop - AgriGuard QR Verify Proxy Route Test

Date: 2026-07-04
App: AgriGuard
Cycle: Public QR verification API proxy contract

## Baseline

After adopting `/api` as the frontend API base URL, normal backend root routes such as `/products/` resolve through the same-origin proxy as `/api/products/`. Public QR verification is different: the backend route itself is `/api/qr/{token}/verify`, so the browser-side proxied URL must remain `/api/api/qr/{token}/verify`.

That prefix shape is easy to break during cleanup unless it has focused coverage.

## Variant

Added `qrVerifyApi` coverage to `api.test.js`:

- MSW only handles the proxied route shape: `/api/api/qr/{token}/verify`.
- The test verifies QR token, session id, source, and variant query propagation.
- Product API proxy tests continue to cover root backend routes through `/api/products/...`.

## Evidence

- `npm run test -- api.test.js`
  - Test files: 1 passed
  - Tests: 5 passed
- `npm run lint`
  - Status: pass

## Decision

Adopt the QR verify proxy route test. It preserves the intentional frontend `/api` proxy plus backend `/api/qr` route contract.
