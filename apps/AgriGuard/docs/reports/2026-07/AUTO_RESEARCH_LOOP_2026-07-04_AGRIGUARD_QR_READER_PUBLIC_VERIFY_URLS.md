# AutoResearch Loop - AgriGuard QR Reader Public Verify URLs

Date: 2026-07-04
App: AgriGuard
Cycle: Scanner URL parsing regression coverage

## Baseline

`QRReader` had tests for product URLs, `agri://verify/{token}` QR values, bare manual tokens, and malformed manual input. Production labels can also contain full public verify URLs such as `https://verify.agriguard.test/verify/{token}` when `PUBLIC_VERIFY_BASE_URL` is configured.

That full public verify URL path was supported by code but not locked by tests.

## Variant

Added QR reader tests for full public verify URLs:

- Scanner callback with `https://verify.agriguard.test/verify/prod-3?utm=label`
- Manual entry with `https://verify.agriguard.test/verify/manual-token?utm=label`

Both paths must navigate to the local `/verify/{token}` route while preserving scan analytics query parameters.

## Evidence

- `npm run test -- QRReader.test.jsx`
  - Test files: 1 passed
  - Tests: 10 passed
- `npm run lint`
  - Status: pass

## Decision

Adopt the public verify URL coverage. It protects scanner compatibility with production QR labels generated from a configured public verify base URL.
