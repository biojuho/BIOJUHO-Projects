# AutoResearch Loop - AgriGuard Dashboard Auth and SW Refresh

Date: 2026-07-04

## Hypothesis

Manual browser review of the dashboard without an operator token surfaced a launch-readiness UX issue: a protected dashboard summary returning HTTP 401 was shown as a backend outage. While verifying the fix against `vite preview`, the existing service worker also kept serving a stale app shell from cache. This could make post-deploy fixes invisible to returning users.

## Changes

- Added dashboard load-error classification in `Dashboard.jsx`.
  - HTTP 401 now renders `Operator authentication required`.
  - Non-auth failures still render the existing backend connection failure message.
- Added dashboard tests for:
  - core dashboard Korean copy rendering without mojibake regressions;
  - protected summary 401 rendering as operator auth, not backend outage.
- Changed `public/sw.js` from cache-first app-shell handling to network-first handling for `/` and `/index.html`.
  - Hashed assets, icons, and manifest remain cache-first.
  - Cache namespace bumped from `agriguard-v3` to `agriguard-v4`.
- Added `src/serviceWorkerPolicy.test.js` to lock the app-shell/static-asset cache split.

## Verification

- `npm run test -- Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - 2 files passed, 5 tests passed.
- `npx eslint src/components/dashboard/Dashboard.jsx src/components/dashboard/Dashboard.test.jsx src/serviceWorkerPolicy.test.js`
  - passed.
- `npm run build`
  - passed; generated `Dashboard-CNipsfw7.js` and copied `sw.js`.
- Served SW check:
  - `http://127.0.0.1:5174/sw.js` contains `agriguard-v4`, `isAppShellRequest`, and network-first `fetch(request)` branch.
- Manual Playwright evidence:
  - `http://127.0.0.1:5174/?cache-bust=dashboard-auth-sw-network-first` rendered `Operator authentication required`.
  - After SW refresh, plain `http://127.0.0.1:5174/` also rendered `Operator authentication required`.
- Browser smoke:
  - `var/agriguard-browser-smoke-suite-dashboard-auth-sw-network-first.json`
  - status `pass`; 5/5 steps passed; 121/121 checks passed; 2/2 prechecks passed.
- Workspace smoke:
  - `var/workspace-smoke-agriguard-dashboard-auth-sw-network-first-complete.json`
  - status `complete`; 5/5 checks passed.
- Guarded launch status:
  - `var/agriguard-guarded-launch-status-dashboard-auth-sw-network-first.json`
  - status `blocked`; blocker class `preflight_blocked`.
  - Env validation remains ready for preflight with 0 placeholders.
  - Remaining operator action: `set_firebase_service_account_file`.
  - Remaining preflight error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Launch Readiness Result

This loop removes a real launch UX defect and a stale-app-shell deployment risk. Local UI, browser, build, and AgriGuard scope smoke evidence are green. The launch path remains intentionally blocked only on the external Firebase Admin service-account JSON file.
