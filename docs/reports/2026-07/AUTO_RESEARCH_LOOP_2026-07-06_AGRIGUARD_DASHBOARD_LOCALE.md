# AutoResearch Loop - AgriGuard Dashboard Locale

Date: 2026-07-06

## Scope

Remove mixed Korean/host-locale copy from the English AgriGuard dashboard first viewport and make QR trend dates deterministic for launch screenshots.

## Changes

- Replaced dashboard header, live badge, summary card labels, chart titles, empty states, and backend-error copy with English text.
- Pinned dashboard QR trend dates to `en-US` so host browser locale cannot render Korean month/day text.
- Updated dashboard tests to assert the English heading, summary labels, and `Jun 10` trend date.

## Verification

- `rg -n "\p{Hangul}" apps/AgriGuard/frontend/src/components/dashboard/Dashboard.jsx apps/AgriGuard/frontend/src/components/dashboard/Dashboard.test.jsx`
  - Result: no matches.
- `npm.cmd test -- --run src/components/dashboard/Dashboard.test.jsx`
  - Result: 1 file passed, 6 tests passed.
- `npm.cmd run lint -- src/components/dashboard/Dashboard.jsx src/components/dashboard/Dashboard.test.jsx`
  - Result: 0 errors, 1 existing warning in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5284 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-dashboard-locale-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-dashboard-locale-mobile-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 PASS.
  - Dashboard screenshot shows `AgriGuard Supply Chain Status`, `Live data`, and `Jun 30`, `Jul 01`, `Jul 02` QR trend dates.
  - JSON evidence contains no Korean characters and no old Korean dashboard heading/badge.
- `npm.cmd test -- --run`
  - Result: 18 files passed, 101 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5284 --api-url http://127.0.0.1:8014 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-dashboard-locale-mobile --json-out var/agriguard-browser-smoke-dashboard-locale-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 191/191 checks passed, 19/19 screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: upstream unchanged at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-dashboard-locale-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DASHBOARD_LOCALE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var/agriguard-guarded-launch-status-dashboard-locale-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Remaining Blocker

Strict guarded launch still fails closed because the operator-provided Firebase Admin service-account file is missing:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
