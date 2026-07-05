# AutoResearch Loop - AgriGuard Mobile Toast Snackbar

Date: 2026-07-06

## Hypothesis

Mobile toast notifications should not cover the fixed app header or the dashboard title. The previous top-right toast placement shared the header area on narrow screens, obscuring the auth-recovery dashboard view during launch smoke verification.

## A/B Result

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-manual-disabled-mobile/dashboard-auth-recovery.png`
- Intermediate screenshot: `var/agriguard-dashboard-auth-toast-mobile-2026-07-06.png`
- Variant screenshot: `var/agriguard-dashboard-auth-toast-bottom-mobile-2026-07-06.png`
- Aggregate variant screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-mobile/dashboard-auth-recovery.png`

Result: mobile toasts now render as bottom snackbars. The fixed header and dashboard title remain visible, while desktop retains the existing top-right placement.

## Changes

- `apps/AgriGuard/frontend/src/components/ui/Toast.jsx`
  - Changed mobile placement to `bottom-4 inset-x-4`.
  - Kept desktop placement as `sm:top-6 sm:right-6`.
  - Added mobile width constraints so the snackbar fits narrow viewports without edge contact.
- `apps/AgriGuard/frontend/src/components/ui/Toast.test.jsx`
  - Added responsive placement coverage for the mobile snackbar and desktop top-right classes.

## Verification

- `npm test -- Toast.test.jsx`: 1 file passed, 1 test passed.
- `npx eslint src/components/ui/Toast.jsx src/components/ui/Toast.test.jsx`: passed.
- `python apps/AgriGuard/scripts/dashboard_auth_browser_smoke.py --base-url http://127.0.0.1:5201 --operator-token browser-smoke-token --mobile --json-out var/agriguard-dashboard-auth-toast-bottom-mobile-2026-07-06.json --screenshot var/agriguard-dashboard-auth-toast-bottom-mobile-2026-07-06.png --timeout-ms 120000`: passed, 14/14 checks.
- `npm test -- --run`: 17 files passed, 91 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5202 --api-url http://127.0.0.1:8020 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5202 --api-url http://127.0.0.1:8020 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-toast-bottom-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-toast-bottom.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
