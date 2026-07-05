# AutoResearch Loop: AgriGuard E2E Operator Token Smoke

Date: 2026-07-06

## Change

- Aligned the Playwright spec with the current ESM frontend test environment.
- Used role-based navigation assertions and a collapsed-menu helper for desktop/mobile parity.
- Seeded `agriguard-operator-token` in Playwright E2E setup using `AGRIGUARD_BROWSER_OPERATOR_TOKEN` or the local browser-smoke default `browser-smoke-token`.
- Strengthened the supply-chain route test to assert the `Supply Chain Overview` heading, not only the URL.

## Verification

- `npx playwright test`
  - Result: `12 passed`

## Evidence

- The full Playwright matrix covered Chromium desktop and Pixel 5 mobile.
- E2E setup now matches the operator-token behavior used by AgriGuard browser-smoke scripts.
- The supply-chain route check now verifies visible page content after navigation.
- The previous unauthenticated supply-chain `401` console noise did not recur in the passing run.

## Remaining External Blocker

Real compose/browser launch remains blocked until the operator provides a real Firebase Admin service-account `.json` at an absolute host path outside the repo for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
