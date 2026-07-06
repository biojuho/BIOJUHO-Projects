# AutoResearch Loop - AgriGuard Desktop Aggregate Pass - 2026-07-06

## Scope

Run the aggregate AgriGuard browser smoke suite in desktop mode after the mobile aggregate fixes and QR token clear-label polish.

## Evidence

- Command:
  `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5277 --api-url http://127.0.0.1:8007 --include-unavailable-check --output-dir var/agriguard-browser-smoke-suite-2026-07-06-desktop-post-label --json-out var/agriguard-browser-smoke-suite-2026-07-06-desktop-post-label.json --timeout-ms 30000`
- Result: `175/175` checks passed.
- Browser steps: `7/7` passed.
- Prechecks: `3/3` passed.
- Screenshot artifacts: `19/19` present with no dimension failures.

The run used a disposable backend on `127.0.0.1:8007`, Vite on `127.0.0.1:5277`, and `VITE_PROXY_API_TARGET=http://127.0.0.1:8007` so frontend `/api` traffic exercised the fresh backend code while remaining same-origin in the browser.

## Prior Evidence In Same Loop

- Mobile aggregate after fixes: `var/agriguard-browser-smoke-suite-2026-07-06-aggregate-fix.json`, `191/191` checks passed.
- QR token clear-label mobile nav smoke: `var/agriguard-nav-browser-smoke-qr-token-clear-label.json`, `65/65` checks passed.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
