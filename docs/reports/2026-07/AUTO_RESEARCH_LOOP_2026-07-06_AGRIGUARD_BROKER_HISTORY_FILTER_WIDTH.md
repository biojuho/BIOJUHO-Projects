# AutoResearch Loop - AgriGuard Broker History Filter Width - 2026-07-06

## Scope

- Hardened the broker provisioning evidence history filter input in `SensorDeviceManager.jsx`.
- Replaced the mobile fixed `min-w-64` with `min-w-0 w-full`.
- Preserved the desktop minimum width with `sm:min-w-64`.
- Added regression coverage for the responsive filter input classes.

## Verification

- Focused sensor manager test: `npm.cmd test -- --run SensorDeviceManager.test.jsx`
  - Result: 1 file passed, 22 tests passed.
- Focused sensor manager lint: `npm.cmd run lint -- src/components/SensorDeviceManager.jsx src/components/SensorDeviceManager.test.jsx`
  - Result: 0 errors.
  - Existing warning retained: `react-refresh/only-export-components` in `Dashboard.jsx`.
- Full frontend suite: `npm.cmd test -- --run`
  - Result: 18 files passed, 103 tests passed.
- Mobile nav browser smoke: `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5305 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-broker-history-filter-width.json --screenshot-dir var/agriguard-nav-browser-smoke-broker-history-filter-width-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 checks passed.
- Aggregate mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5305 --api-url http://127.0.0.1:8035 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-broker-history-filter-width --json-out var/agriguard-browser-smoke-broker-history-filter-width.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 191/191 checks passed, 7/7 steps passed, 19/19 screenshot artifacts passed.

## Source Tracking

- Upstream AutoResearch source check:
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-broker-history-filter-width-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROKER_HISTORY_FILTER_WIDTH_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8, partially_adopted=0, watch=0.

## Guarded Launch Status

- Command: `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-broker-history-filter-width-2026-07-06.json`
- Result: still blocked at strict launch preflight by operator-owned Firebase service-account material.
- Blocking action id: `set_firebase_service_account_file`.
- Blocking error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
