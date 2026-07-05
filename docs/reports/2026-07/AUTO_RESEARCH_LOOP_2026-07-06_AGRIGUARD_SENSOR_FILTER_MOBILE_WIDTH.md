# AutoResearch Loop - AgriGuard Mobile Sensor Filter Width

Date: 2026-07-06

## Hypothesis

The mobile sensor registry filter panel should prefer one full-width control per row under the `sm` breakpoint. The previous two-column mobile grid compressed the zone filter, making generated smoke-zone values hard to read in the first viewport even though automated route checks passed.

## A/B Result

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-token-precheck-mobile/admin-routes-screens/sensor-devices.png`
- Variant screenshot: `var/agriguard-admin-routes-sensor-filter-mobile-2026-07-06/sensor-devices.png`
- Aggregate variant screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-mobile/admin-routes-screens/sensor-devices.png`

Result: the variant renders `Sensor state`, `Zone filter`, and `Apply filters` as full-width mobile rows. The zone value remains readable in the mobile first viewport while retaining the existing two-column `sm` layout and desktop `lg` layout.

## Changes

- `apps/AgriGuard/frontend/src/components/SensorDeviceManager.jsx`
  - Changed the filter form from `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`.
  - Moved the submit button span to `sm:col-span-2 lg:col-span-1`.
- `apps/AgriGuard/frontend/src/components/SensorDeviceManager.test.jsx`
  - Updated the compact mobile controls assertion to lock the full-width default and responsive spans.

## Verification

- `npm test -- SensorDeviceManager.test.jsx`: 1 file passed, 20 tests passed.
- `npx eslint src/components/SensorDeviceManager.jsx src/components/SensorDeviceManager.test.jsx`: passed.
- `npm test -- --run`: 16 files passed, 89 tests passed.
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5185 --api-url http://127.0.0.1:8003 --mobile --json-out var/agriguard-admin-routes-sensor-filter-mobile-2026-07-06.json --screenshot-dir var/agriguard-admin-routes-sensor-filter-mobile-2026-07-06 --timeout-ms 120000`: passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5195 --api-url http://127.0.0.1:8013 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5195 --api-url http://127.0.0.1:8013 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-sensor-filter-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-sensor-filter-mobile.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
