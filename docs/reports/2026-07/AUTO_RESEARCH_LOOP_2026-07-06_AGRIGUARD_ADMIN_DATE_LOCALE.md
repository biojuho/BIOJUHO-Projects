# AutoResearch Loop - AgriGuard Admin Date Locale

Date: 2026-07-06

## Scope

Normalize the remaining implicit operator admin date/time formatters in QR Tokens and Sensor Devices so launch/admin screens do not depend on host browser locale.

## Changes

- Replaced QR Token date/time formatting with explicit `en-US` `Intl.DateTimeFormat`.
- Replaced Sensor Device date/time formatting with explicit `en-US` `Intl.DateTimeFormat`.
- Added QR Token and Sensor Device tests for expected English operator dates and Korean date marker rejection.
- Confirmed no remaining implicit or Korean component date formatters with the targeted source scan.

## Verification

- `npm.cmd test -- --run QRTokenManager.test.jsx SensorDeviceManager.test.jsx`
  - Result: 2 files passed, 27 tests passed.
- `npm.cmd run lint -- src/components/QRTokenManager.jsx src/components/QRTokenManager.test.jsx src/components/SensorDeviceManager.jsx src/components/SensorDeviceManager.test.jsx`
  - Result: 0 errors, 1 existing warning in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `rg -n "toLocale(DateString|String|TimeString)\(undefined|Intl\.DateTimeFormat\(undefined|toLocale(DateString|String|TimeString)\('ko-KR'" apps/AgriGuard/frontend/src/components -g "*.jsx"`
  - Result: no matches.
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5288 --api-url http://127.0.0.1:8018 --operator-token browser-smoke-token --json-out var/agriguard-admin-routes-browser-smoke-admin-date-locale.json --screenshot-dir var/agriguard-admin-routes-browser-smoke-admin-date-locale-screens --timeout-ms 30000 --mobile`
  - Result: 17/17 PASS; no Korean date markers in the admin routes JSON.
- `npm.cmd test -- --run`
  - Result: 18 files passed, 101 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5288 --api-url http://127.0.0.1:8018 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-admin-date-locale-mobile --json-out var/agriguard-browser-smoke-admin-date-locale-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 191/191 checks passed, 19/19 screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: upstream unchanged at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-admin-date-locale-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ADMIN_DATE_LOCALE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var/agriguard-guarded-launch-status-admin-date-locale-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Remaining Blocker

Strict guarded launch still fails closed because the operator-provided Firebase Admin service-account file is missing:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
