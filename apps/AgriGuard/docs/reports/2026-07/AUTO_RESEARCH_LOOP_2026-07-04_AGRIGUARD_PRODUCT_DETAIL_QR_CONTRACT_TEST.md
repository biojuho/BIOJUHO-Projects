# AutoResearch Loop - AgriGuard Product Detail QR Contract Test

Date: 2026-07-04
App: AgriGuard
Cycle: Product detail QR regression coverage

## Baseline

The product detail browser smoke proved local QR rendering, but the component unit test only checked the surrounding product details and operator controls. A future regression could reintroduce a remote QR image without failing the focused ProductDetail test.

## Variant

Added local QR contract assertions to `ProductDetail.test.jsx`:

- The product detail view exposes `Product verification QR` as an accessible image.
- The product QR value remains visible to the user.
- The old `alt="QR Code"` remote-image path is absent.
- No image URL targeting `api.qrserver.com` is rendered.

## Evidence

- `npm run test -- ProductDetail.test.jsx`
  - Test files: 1 passed
  - Tests: 6 passed
- `npm run lint`
  - Status: pass

## Decision

Adopt the ProductDetail QR contract test. It gives the local QR rendering behavior a fast regression gate in addition to the browser smoke.
