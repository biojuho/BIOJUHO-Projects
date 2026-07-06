# AutoResearch Loop - AgriGuard Registry Bottom Margin - 2026-07-06

## Scope

Apply the first-viewport CTA clearance rule to the mobile crop registry form after screenshot review showed the primary `Register Harvest` button was fully visible but too close to the viewport bottom.

## Findings

- Baseline mobile registry measurement from the scanner-margin aggregate: `Register Harvest` button `bottom=835` in an `844`px viewport, leaving `9`px bottom clearance.
- The old visible-ratio check passed, but the CTA had less breathing room than the scanner recovery CTA now requires.

## Changes

- `nav_browser_smoke.py` now requires `min_bottom_margin=16` for the registry `Register Harvest` affordance.
- `test_smoke.py` locks the registry bottom-margin requirement.
- `ProductRegistry` shortens the mobile description textarea from `h-20` to `h-16`, keeping `sm:h-32` unchanged for larger viewports.
- `ProductRegistry.test.jsx` asserts the updated mobile textarea height.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_nav_browser_smoke_tracks_mobile_first_viewport_affordances -q`: `1` passed.
- `python -m py_compile apps/AgriGuard/scripts/nav_browser_smoke.py`: passed.
- `npm.cmd test -- --run ProductRegistry.test.jsx`: `1` file, `1` test passed.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5282 --operator-token browser-smoke-token --click-nav --mobile --json-out var/agriguard-nav-browser-smoke-registry-margin-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-registry-margin-mobile-screens --timeout-ms 30000`: `65/65` passed.
- Final registry measurement: `Register Harvest` button `top=771`, `bottom=819`, `height=48`, `visibleHeight=48`, `visibleRatio=1`, `bottomMargin=25`, `minBottomMargin=16`.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`: `56` passed.
- `npm.cmd test -- --run`: `18` files, `101` tests passed.
- `npm.cmd run lint -- src/components/ProductRegistry.jsx src/components/ProductRegistry.test.jsx`: no errors; existing warning remains in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5282 --api-url http://127.0.0.1:8012 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-registry-margin-mobile --json-out var/agriguard-browser-smoke-registry-margin-mobile.json --timeout-ms 30000 --mobile --include-unavailable-check`: `7/7` steps passed, `191/191` checks passed, `19/19` screenshot artifacts passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-registry-margin-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_REGISTRY_MARGIN_2026-07-06.md`: valid, `8` sources, `8` adopted.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
