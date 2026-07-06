# AutoResearch Loop - AgriGuard Cold-Chain Locale

Date: 2026-07-06

## Scope

Remove the remaining explicit Korean date/time formatting from the Cold-Chain Monitor so live sensor timelines and zone last-seen values stay English in launch/operator screens.

## Changes

- Replaced `ko-KR` last-seen formatting with explicit `en-US` `Intl.DateTimeFormat`.
- Replaced `ko-KR` chart time labels with explicit `en-US` formatting.
- Added ColdChain test coverage for the English last-seen value and Korean date marker rejection.

## Verification

- `npm.cmd test -- --run ColdChainMonitor.test.jsx`
  - Result: 1 file passed, 6 tests passed.
- `npm.cmd run lint -- src/components/ColdChainMonitor.jsx src/components/ColdChainMonitor.test.jsx`
  - Result: 0 errors, 1 existing warning in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5287 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-cold-chain-locale-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-cold-chain-locale-mobile-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 PASS; no Korean date markers in the nav JSON.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5287 --api-url http://127.0.0.1:8017 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-cold-chain-locale-mobile --json-out var/agriguard-browser-smoke-cold-chain-locale-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 191/191 checks passed, 19/19 screenshot artifacts passed.
- `npm.cmd test -- --run`
  - Result: 18 files passed, 101 tests passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: upstream unchanged at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-cold-chain-locale-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COLD_CHAIN_LOCALE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var/agriguard-guarded-launch-status-cold-chain-locale-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Remaining Blocker

Strict guarded launch still fails closed because the operator-provided Firebase Admin service-account file is missing:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
