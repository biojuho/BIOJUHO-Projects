# AutoResearch Loop - AgriGuard Unsupported Sensor Mobile Table - 2026-07-06

## Scope

- Converted the unsupported broker identities cleanup table in `SensorDeviceManager.jsx` from a mobile horizontal-scroll table to mobile-first card rows.
- Kept the desktop table layout with `md:min-w-[680px]`.
- Removed mobile-only fixed action-panel width by using `min-w-0` on mobile and `md:min-w-64` on desktop.
- Added regression coverage for the responsive table, row labels, action panel width, and inspectable unsupported sensor values.

## Verification

- Focused sensor manager test: `npm.cmd test -- --run SensorDeviceManager.test.jsx`
  - Result: 1 file passed, 21 tests passed.
- Focused sensor manager lint: `npm.cmd run lint -- src/components/SensorDeviceManager.jsx src/components/SensorDeviceManager.test.jsx`
  - Result: 0 errors.
  - Existing warning retained: `react-refresh/only-export-components` in `Dashboard.jsx`.
- Full frontend suite: `npm.cmd test -- --run`
  - Result: 18 files passed, 102 tests passed.
- Mobile nav browser smoke: `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5302 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-unsupported-sensor-mobile-table.json --screenshot-dir var/agriguard-nav-browser-smoke-unsupported-sensor-mobile-table-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 checks passed.
- Admin route browser smoke rerun: `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5302 --api-url http://127.0.0.1:8032 --operator-token browser-smoke-token --json-out var/agriguard-admin-routes-unsupported-sensor-mobile-table-rerun.json --screenshot-dir var/agriguard-admin-routes-unsupported-sensor-mobile-table-rerun-screens --timeout-ms 30000 --mobile`
  - Result: passed.
- Aggregate mobile browser suite rerun: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5302 --api-url http://127.0.0.1:8032 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-unsupported-sensor-mobile-table-rerun --json-out var/agriguard-browser-smoke-unsupported-sensor-mobile-table-rerun.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 191/191 checks passed, 7/7 steps passed, 19/19 screenshot artifacts passed.

## Transient Retry Note

- The first aggregate run reported one failed `admin_routes` step because Vite returned one transient `net::ERR_CONNECTION_FAILED` resource load for `index.html?html-proxy&index=0.js`.
- The backend route log showed expected anonymous 401 checks followed by successful authorized retries.
- The standalone `admin_routes` rerun passed, and the aggregate rerun passed 191/191.

## Source Tracking

- Upstream AutoResearch source check:
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-unsupported-sensor-mobile-table-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_UNSUPPORTED_SENSOR_MOBILE_TABLE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8, partially_adopted=0, watch=0.

## Guarded Launch Status

- Command: `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-unsupported-sensor-mobile-table-2026-07-06.json`
- Result: still blocked at strict launch preflight by operator-owned Firebase service-account material.
- Blocking action id: `set_firebase_service_account_file`.
- Blocking error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
