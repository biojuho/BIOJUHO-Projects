# AutoResearch Loop - AgriGuard Dashboard Auth Copy Inline Retry

Date: 2026-07-04

## Hypothesis

After adding inline token save-and-retry on the dashboard auth error, the old copy still told operators to save a token elsewhere and reload the dashboard. The copy should match the current recovery path.

## Changes

- Updated the dashboard auth-error description to: `Paste a Firebase/operator token below, or save one in QR Tokens or Sensors.`
- Updated `Dashboard.test.jsx` to assert the new recovery copy.

## Verification

- `npm run test -- Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - 2 files passed, 6 tests passed.
- `npx eslint src/components/dashboard/Dashboard.jsx src/components/dashboard/Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - passed.
- `npm run build`
  - passed; generated `Dashboard-CcwpMksq.js`.
- Browser smoke:
  - `var/agriguard-browser-smoke-suite-dashboard-auth-copy-inline-retry.json`
  - 5/5 steps passed; 121/121 checks passed; 2/2 prechecks passed.
- Manual Playwright mobile snapshot at 390px:
  - heading `Operator authentication required`;
  - description `Paste a Firebase/operator token below, or save one in QR Tokens or Sensors.`;
  - textbox `Operator bearer token`;
  - button `Save and retry`.

## Launch Readiness Result

This loop aligns first-screen auth recovery copy with the actual inline retry behavior. No launch blocker changed; the remaining blocker is still the external Firebase Admin service-account JSON file.
