# AutoResearch Loop - AgriGuard Consumer Trust Badge Copy

Date: 2026-07-06

## Hypothesis

Consumer-facing trust badges should use plain public status copy instead of exposing the raw API `Unknown` status. Registered QR codes with incomplete evidence should read differently from invalid or fake QR codes.

## A/B Result

- Baseline pending screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-mobile/qr-path-screens/manual-verify.png`
- Variant focused screenshots: `var/agriguard-qr-path-consumer-badge-mobile-2026-07-06/manual-verify.png`, `var/agriguard-qr-path-consumer-badge-mobile-2026-07-06/invalid-verify.png`
- Aggregate variant screenshots: `var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-mobile/qr-path-screens/manual-verify.png`, `var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-mobile/qr-path-screens/invalid-verify.png`

Result: registered QR codes with delayed public evidence now show `Evidence pending`, while invalid or fake QR codes show `Not verified`. API status semantics remain unchanged.

## Changes

- `apps/AgriGuard/frontend/src/components/ConsumerVerify.jsx`
  - Added public trust-badge label mapping for `Unknown` trust states.
  - Added a test id for the rendered trust badge to support stable UI assertions.
- `apps/AgriGuard/frontend/src/components/ConsumerVerify.test.jsx`
  - Covered safe, invalid, and registered-but-pending public badge copy.

## Verification

- `npm test -- ConsumerVerify.test.jsx`: 1 file passed, 3 tests passed.
- `npx eslint src/components/ConsumerVerify.jsx src/components/ConsumerVerify.test.jsx`: passed.
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5203 --api-url http://127.0.0.1:8021 --json-out var/agriguard-qr-path-consumer-badge-mobile-2026-07-06.json --screenshot-dir var/agriguard-qr-path-consumer-badge-mobile-2026-07-06 --timeout-ms 120000`: passed, 27/27 checks.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5204 --api-url http://127.0.0.1:8022 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5204 --api-url http://127.0.0.1:8022 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-consumer-badge-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-consumer-badge.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
