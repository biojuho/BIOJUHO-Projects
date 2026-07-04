# AutoResearch Loop - AgriGuard Dashboard Inline Token Retry

Date: 2026-07-04

## Hypothesis

After classifying dashboard HTTP 401 responses as an operator-auth issue, the first screen still required users to navigate elsewhere to recover. For launch readiness, the protected dashboard should give operators a direct path to save a Firebase/operator bearer token and retry the metrics request.

## Changes

- Added an inline operator-token form to the dashboard auth-error state.
  - The form is shown only for classified auth failures.
  - It reuses the existing `getOperatorToken` / `setOperatorToken` local-storage contract from QR Tokens and Sensors.
  - Submitting saves the token, clears the error, shows loading state, and retries `/dashboard/summary`.
- Refactored dashboard summary loading into a reusable fetch callback without adding a new auth mechanism.
- Extended `Dashboard.test.jsx` to verify:
  - the auth-error state includes the token input;
  - saving a token calls `setOperatorToken`;
  - the dashboard summary request is retried and returns to the normal dashboard state.

## Verification

- `npm run test -- Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - 2 files passed, 6 tests passed.
- `npx eslint src/components/dashboard/Dashboard.jsx src/components/dashboard/Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - passed.
- `npm run build`
  - passed; generated `Dashboard-DduILCyg.js`.
- Manual Playwright accessibility snapshot for `http://127.0.0.1:5174/`:
  - heading `Operator authentication required`;
  - textbox `Operator bearer token`;
  - button `Save and retry`;
  - explanatory local-storage copy.
- Browser smoke:
  - `var/agriguard-browser-smoke-suite-dashboard-inline-token-retry.json`
  - 5/5 steps passed; 121/121 checks passed; 2/2 prechecks passed.
- Workspace smoke:
  - `var/workspace-smoke-agriguard-dashboard-inline-token-retry.json`
  - 5/5 AgriGuard checks passed.
- Guarded launch status:
  - `var/agriguard-guarded-launch-status-dashboard-inline-token-retry.json`
  - status `blocked`; blocker class `preflight_blocked`;
  - env validation ready for preflight with 0 placeholders;
  - remaining operator action `set_firebase_service_account_file`;
  - remaining preflight error `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Launch Readiness Result

This loop improves first-screen recovery for authorized operators without changing the backend auth contract. Local tests, build, browser smoke, Playwright UI inspection, and full AgriGuard smoke are green. Launch remains blocked only on the external Firebase Admin service-account JSON file.
