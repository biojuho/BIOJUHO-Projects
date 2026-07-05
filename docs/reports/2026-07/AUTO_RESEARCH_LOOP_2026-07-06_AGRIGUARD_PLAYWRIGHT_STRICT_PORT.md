# AutoResearch Loop: AgriGuard Playwright Strict Port

Date: 2026-07-06

## Change

- Updated AgriGuard frontend Playwright config to use an app-specific strict Vite port.
- Disabled Playwright web-server reuse so E2E tests cannot accidentally attach to another local app already running on `localhost:5173`.
- Added `AGRIGUARD_E2E_HOST` and `AGRIGUARD_E2E_PORT` environment overrides while defaulting to `127.0.0.1:5183`.

## Verification

- Baseline failure before the change:
  - `npx playwright test --project=chromium`
  - Result: `3 failed, 3 passed`
  - Cause: Playwright reused an existing `localhost:5173` server that rendered a DSCI app instead of AgriGuard.
- Desktop browser verification after the change:
  - `npx playwright test --project=chromium`
  - Result: `6 passed`
- Mobile browser verification after the change:
  - `npx playwright test --project=mobile`
  - Result: `6 passed`

## Evidence

- The passing E2E runs started Vite on `127.0.0.1:5183`.
- Route smoke covered dashboard load, navigation links, registry route, QR scanner route, supply-chain route, and unknown-route redirect.
- Mobile run emitted unauthenticated supply-chain `401` console errors, but all route smoke assertions passed.

## Remaining External Blocker

Real compose/browser launch remains blocked until the operator provides a real Firebase Admin service-account `.json` at an absolute host path outside the repo for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
