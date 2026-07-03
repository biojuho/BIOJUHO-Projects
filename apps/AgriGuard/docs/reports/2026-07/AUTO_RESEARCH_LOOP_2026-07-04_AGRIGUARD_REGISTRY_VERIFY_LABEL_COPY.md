# AutoResearch Loop - AgriGuard Registry Verify Label Copy

Date: 2026-07-04
App: AgriGuard
Cycle: Product registration success copy

## Baseline

After a product registration succeeds, the registry displayed the returned `qr_code` value with a `TX:` prefix. The returned value is the public verify QR label URL/token, not a blockchain transaction hash.

Risk:

- Operators could misread the value as a transaction id instead of the consumer-facing QR label.
- A production public verify URL could be hidden behind misleading copy.

## Variant

Updated the success state:

- The issued QR value is labeled `Public verify label`.
- The misleading `TX:` prefix was removed.
- Added `ProductRegistry.test.jsx` to verify the registration call and success output.

## Evidence

- `npm run test -- ProductRegistry.test.jsx`
  - Test files: 1 passed
  - Tests: 1 passed
- `npm run lint`
  - Status: pass
- `npm run build:lts`
  - Status: pass

## Decision

Adopt the clearer public verify label copy. It matches what the backend returns and what operators need to put on product labels.
