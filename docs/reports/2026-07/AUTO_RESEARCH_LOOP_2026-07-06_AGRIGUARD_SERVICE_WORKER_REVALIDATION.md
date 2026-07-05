# Auto Research Loop - AgriGuard Service Worker Revalidation

Date: 2026-07-06

## Source Basis

- Chrome service-worker update guidance documents `updateViaCache: "none"` as the option that avoids consulting the HTTP cache for the top-level service worker script and imported scripts during update checks.
- MDN Cache-Control guidance defines `no-cache` as reusable only after origin revalidation, which is the right fit for `/sw.js` because installed PWAs need launch fixes promptly while static hashed assets can remain immutable.

## Change

- Changed production service-worker registration in `apps/AgriGuard/frontend/index.html` to:
  - `navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" })`
- Added an exact nginx `location = /sw.js` block in `apps/AgriGuard/frontend/nginx.conf`.
  - The worker script now receives `Cache-Control: no-cache` and the same baseline security headers as the SPA shell.
  - This keeps `/sw.js` out of the generic long-lived `.js` immutable asset rule.
- Extended `apps/AgriGuard/frontend/src/serviceWorkerPolicy.test.js` to lock down both the registration option and nginx revalidation header.

## Verification

- Failing-first:
  - `npm run test -- --run src/serviceWorkerPolicy.test.js`
  - Result: failed before the fix because `updateViaCache: "none"` and `location = /sw.js` were absent.
- Passing focused check:
  - `npm run test -- --run src/serviceWorkerPolicy.test.js`
  - Result: `4 passed`.
- Frontend lint:
  - `npm run lint`
  - Result: pass with one existing warning in `src/components/dashboard/Dashboard.jsx` (`react-refresh/only-export-components`).
- Frontend production build:
  - `npm run build:lts`
  - Result: pass.

## Current Launch Blocker

This closes a PWA update-staleness risk for installed clients. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
