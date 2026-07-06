# AutoResearch Loop - AgriGuard Consumer Locale

Date: 2026-07-06

## Scope

Normalize English-facing AgriGuard consumer/product verification dates so public and operator product-detail screens do not inherit the host browser locale. During mobile screenshot review, English UI surfaces showed Korean-formatted timestamps such as year and AM/PM markers from the Windows host locale.

## Changes

- Pinned `ConsumerVerify` public verification date and timestamp formatting to `en-US`.
- Pinned `ProductDetail` harvest-date formatting to `en-US`.
- Pinned `ProductTimeline` blockchain and event timestamp formatting to `en-US`.
- Added unit coverage that checks English dates and rejects Korean year markers on the affected screens.
- Normalized admin and product-detail browser smoke request-failure gates so Vite `net::ERR_ABORTED` dependency fetches are recorded but do not fail the actionable request-failure gate.

## Verification

- `npm.cmd test -- --run ConsumerVerify.test.jsx ProductDetail.test.jsx`
  - Result: 2 files passed, 14 tests passed.
- `npm.cmd run lint -- src/components/ConsumerVerify.jsx src/components/ConsumerVerify.test.jsx src/components/ProductDetail.jsx src/components/ProductDetail.test.jsx src/components/ProductTimeline.jsx`
  - Result: 0 errors, 1 existing warning in `src/components/dashboard/Dashboard.jsx`.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_product_detail_browser_smoke_filters_aborted_request_failures apps/AgriGuard/backend/tests/test_smoke.py::test_admin_routes_browser_smoke_filters_aborted_request_failures apps/AgriGuard/backend/tests/test_smoke.py::test_admin_routes_browser_smoke_classifies_expected_missing_auth_console -q`
  - Result: 3 passed.
- `python -m py_compile apps/AgriGuard/scripts/product_detail_browser_smoke.py apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
  - Result: passed.
- `python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5283 --api-url http://127.0.0.1:8013 --operator-token browser-smoke-token --json-out var/agriguard-product-detail-browser-smoke-consumer-locale-final.json --screenshot-dir var/agriguard-product-detail-browser-smoke-consumer-locale-final-screens --timeout-ms 30000 --mobile`
  - Result: pass, 28/28 checks; no Korean year, Korean PM, or Korean AM markers in captured observations.
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5283 --api-url http://127.0.0.1:8013 --operator-token browser-smoke-token --json-out var/agriguard-qr-path-browser-smoke-consumer-locale-final.json --screenshot-dir var/agriguard-qr-path-browser-smoke-consumer-locale-final-screens --timeout-ms 30000`
  - Result: 27/27 PASS; no Korean locale markers in captured observations.
- `npm.cmd test -- --run`
  - Result: 18 files passed, 101 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5283 --api-url http://127.0.0.1:8013 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-consumer-locale-mobile-final --json-out var/agriguard-browser-smoke-consumer-locale-mobile-final.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 191/191 checks passed, 19/19 screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: upstream unchanged at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-consumer-locale-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONSUMER_LOCALE_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var/agriguard-guarded-launch-status-consumer-locale-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Remaining Blocker

Strict guarded launch still fails closed because the operator-provided Firebase Admin service-account file is missing:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
