# AutoResearch Loop - AgriGuard QR Reader Disabled Manual Action

Date: 2026-07-06

## Hypothesis

The manual verification button should look unavailable until the operator enters a manual QR value. The previous empty state kept the primary green action styling under disabled opacity, which made an unavailable action read too much like an enabled CTA on mobile.

## A/B Result

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-qr-url-mobile/qr-path-screens/scan.png`
- Variant screenshot: `var/agriguard-qr-path-manual-disabled-mobile-2026-07-06/scan.png`
- Aggregate variant screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-mobile/qr-path-screens/scan.png`

Result: the empty manual verification action now renders as a neutral disabled button. It switches back to the green primary action only after a manual token or verification URL is entered.

## Changes

- `apps/AgriGuard/frontend/src/components/QRReader.jsx`
  - Added a derived `manualValueReady` state for the manual QR input.
  - Kept the existing submit guard and navigation behavior.
  - Changed the disabled visual state from green primary to neutral muted styling.
- `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`
  - Added coverage for the disabled neutral state and enabled primary state after input.

## Verification

- `npm test -- QRReader.test.jsx`: 1 file passed, 15 tests passed.
- `npx eslint src/components/QRReader.jsx src/components/QRReader.test.jsx`: passed.
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5198 --api-url http://127.0.0.1:8016 --json-out var/agriguard-qr-path-manual-disabled-mobile-2026-07-06.json --screenshot-dir var/agriguard-qr-path-manual-disabled-mobile-2026-07-06 --timeout-ms 120000`: passed, 27/27 checks.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5199 --api-url http://127.0.0.1:8017 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5199 --api-url http://127.0.0.1:8017 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-manual-disabled.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
