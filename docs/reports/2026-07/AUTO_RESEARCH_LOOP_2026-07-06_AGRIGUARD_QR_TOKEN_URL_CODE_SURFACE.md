# AutoResearch Loop - AgriGuard QR Token URL Code Surface

Date: 2026-07-06

## Hypothesis

The one-time QR label URL should render as a bounded code surface on mobile. The previous `break-all` inline text avoided overflow, but it split redacted and real token values mid-token in the first viewport, reducing confidence during label production.

## A/B Result

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-mobile/admin-routes-screens/qr-tokens.png`
- Variant screenshot: `var/agriguard-admin-routes-qr-url-mobile-2026-07-06/qr-tokens.png`
- Aggregate variant screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-qr-url-mobile/admin-routes-screens/qr-tokens.png`

Result: the variant renders the label URL inside a single-line, horizontally scrollable code field. The URL no longer wraps mid-token, and the copy action remains immediately available in the same card.

## Changes

- `apps/AgriGuard/frontend/src/components/QRTokenManager.jsx`
  - Replaced the plain `break-all` URL line with a bounded, scrollable, single-line code surface.
  - Added `min-w-0` to the result content so the code surface can respect the responsive card width.
- `apps/AgriGuard/frontend/src/components/QRTokenManager.test.jsx`
  - Locked the success URL surface to `overflow-x-auto` and `whitespace-nowrap`.

## Verification

- `npm test -- QRTokenManager.test.jsx`: 1 file passed, 7 tests passed.
- `npx eslint src/components/QRTokenManager.jsx src/components/QRTokenManager.test.jsx`: passed.
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5196 --api-url http://127.0.0.1:8014 --mobile --json-out var/agriguard-admin-routes-qr-url-mobile-2026-07-06.json --screenshot-dir var/agriguard-admin-routes-qr-url-mobile-2026-07-06 --timeout-ms 120000`: passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5197 --api-url http://127.0.0.1:8015 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-qr-url-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-qr-url-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5197 --api-url http://127.0.0.1:8015 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-qr-url-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-qr-url-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-qr-url.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
