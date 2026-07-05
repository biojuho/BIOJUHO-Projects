# AutoResearch Loop - AgriGuard Opaque Fixed Nav

Date: 2026-07-06

## Hypothesis

The fixed mobile nav should remain readable when operator pages scroll underneath it. The previous shared `glass` nav used translucent blur, which let bright page text bleed through the header in scrolled admin screenshots.

## A/B Result

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-coldchain-stream-label-mobile/admin-routes-screens/sensor-devices-missing-token.png`
- Variant focused screenshot: `var/agriguard-admin-routes-opaque-nav-mobile-2026-07-06/sensor-devices-missing-token.png`
- Aggregate variant screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-opaque-nav-mobile/admin-routes-screens/sensor-devices-missing-token.png`

Result: the header remains a solid app shell while the scrolled admin content passes underneath. The AgriGuard logo and mobile menu icon stay legible in the missing-token sensor workflow.

## Changes

- `apps/AgriGuard/frontend/src/components/Layout.jsx`
  - Replaced the fixed nav `glass` class with opaque `bg-background` plus a restrained shadow.
  - Replaced the mobile menu `glass` class with the same opaque shell treatment.
  - Added a `mobile-nav-menu` test id for stable responsive shell assertions.
- `apps/AgriGuard/frontend/src/components/Layout.test.jsx`
  - Added coverage that the fixed nav and mobile menu use opaque background classes and do not use `glass`.

## Verification

- `npm test -- Layout.test.jsx`: 1 file passed, 1 test passed.
- `npx eslint src/components/Layout.jsx src/components/Layout.test.jsx`: passed.
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5209 --api-url http://127.0.0.1:8027 --operator-token browser-smoke-token --mobile --json-out var/agriguard-admin-routes-opaque-nav-mobile-2026-07-06.json --screenshot-dir var/agriguard-admin-routes-opaque-nav-mobile-2026-07-06 --timeout-ms 120000`: passed.
- `npm test -- --run`: 18 files passed, 93 tests passed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5210 --api-url http://127.0.0.1:8028 --include-unavailable-check --json-out var/agriguard-browser-smoke-suite-2026-07-06-opaque-nav-desktop.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-opaque-nav-desktop --timeout-ms 120000`: passed, 7/7 steps, 167/167 checks, 19/19 screenshot artifacts.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5210 --api-url http://127.0.0.1:8028 --include-unavailable-check --mobile --json-out var/agriguard-browser-smoke-suite-2026-07-06-opaque-nav-mobile.json --output-dir var/agriguard-browser-smoke-suite-2026-07-06-opaque-nav-mobile --timeout-ms 120000`: passed, 7/7 steps, 181/181 checks, 19/19 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-opaque-nav.json`: passed, 5/5 checks.

## Remaining External Blocker

Strict guarded launch/compose/browser proof still cannot complete until a real Firebase Admin service-account JSON exists at `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`; the current launch guard fails closed when the configured file path does not exist.
