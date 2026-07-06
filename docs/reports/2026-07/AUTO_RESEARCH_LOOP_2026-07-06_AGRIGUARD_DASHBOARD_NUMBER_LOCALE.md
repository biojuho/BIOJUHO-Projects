# AutoResearch Loop - AgriGuard Dashboard Number Locale

Date: 2026-07-06

## Scope

Normalize Dashboard QR KPI count formatting so scan targets and trend counts do not depend on the browser's host locale.

## Changes

- Added an explicit `en-US` `Intl.NumberFormat` helper for Dashboard counts.
- Replaced remaining Dashboard `toLocaleString()` count render calls.
- Confirmed the Dashboard component no longer contains host-locale `toLocaleString()` calls.

## Verification

- `npm.cmd test -- --run Dashboard.test.jsx`
  - Result: 1 file passed, 6 tests passed.
- `npm.cmd run lint -- src/components/dashboard/Dashboard.jsx src/components/dashboard/Dashboard.test.jsx`
  - Result: 0 errors, 1 existing warning in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `rg -n "toLocaleString\(" apps/AgriGuard/frontend/src/components/dashboard/Dashboard.jsx`
  - Result: no matches.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5299 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-dashboard-number-locale-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-dashboard-number-locale-mobile-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 PASS; Dashboard screenshot showed `Target 1,000 scans in 24 hours`.
- `npm.cmd test -- --run`
  - Result: 18 files passed, 101 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5299 --api-url http://127.0.0.1:8029 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-dashboard-number-locale-mobile --json-out var/agriguard-browser-smoke-dashboard-number-locale-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 191/191 checks passed, 19/19 screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: upstream unchanged at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-dashboard-number-locale-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DASHBOARD_NUMBER_LOCALE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var/agriguard-guarded-launch-status-dashboard-number-locale-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Remaining Blocker

Strict guarded launch still fails closed because the operator-provided Firebase Admin service-account file is missing:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
