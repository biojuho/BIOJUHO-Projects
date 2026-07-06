# AutoResearch Loop - AgriGuard Scanner Bottom Margin - 2026-07-06

## Scope

Harden the mobile scanner first viewport after aggregate screenshots showed the disabled `Verify code` CTA technically visible but nearly flush with the bottom of a `390x844` viewport.

## Findings

- Baseline mobile scanner measurement from `var/agriguard-browser-smoke-next-gap-mobile/nav.json`: `Verify code` button `bottom=841` in an `844`px viewport, leaving `3`px bottom clearance.
- This passed the old `min_visible_ratio=0.98` gate but looked too tight for a launch-critical manual recovery CTA.

## Changes

- `nav_browser_smoke.py` now supports opt-in `min_bottom_margin` checks for route affordances.
- The scanner `Verify code` affordance now requires `min_bottom_margin=16`.
- `QRReader` moves the scanner card from `mt-8` to `mt-4 sm:mt-8`, improving mobile first-viewport clearance without changing desktop spacing.
- Tests lock the scanner bottom-margin spec and the responsive scanner top-spacing classes.
- Calibration note: the first implementation applied bottom-margin checks to tall cards by default; it now enforces bottom margin only for specs that explicitly request it.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_nav_browser_smoke_tracks_mobile_first_viewport_affordances -q`: `1` passed.
- `python -m py_compile apps/AgriGuard/scripts/nav_browser_smoke.py`: passed.
- `npm.cmd test -- --run QRReader.test.jsx`: `1` file, `17` tests passed.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5281 --operator-token browser-smoke-token --click-nav --mobile --json-out var/agriguard-nav-browser-smoke-scanner-margin-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-scanner-margin-mobile-screens --timeout-ms 30000`: `65/65` passed.
- Final scanner measurement: `Verify code` button `top=781`, `bottom=825`, `height=44`, `visibleHeight=44`, `visibleRatio=1`, `bottomMargin=19`, `minBottomMargin=16`.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`: `56` passed.
- `npm.cmd test -- --run`: `18` files, `101` tests passed.
- `npm.cmd run lint -- src/components/QRReader.jsx src/components/QRReader.test.jsx`: no errors; existing warning remains in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5281 --api-url http://127.0.0.1:8011 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-scanner-margin-mobile --json-out var/agriguard-browser-smoke-scanner-margin-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`: `7/7` steps passed, `191/191` checks passed, `19/19` screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-scanner-margin-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_SCANNER_MARGIN_2026-07-06.md`: valid, `8` sources, `8` adopted.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
