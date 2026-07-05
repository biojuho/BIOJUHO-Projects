# AutoResearch Loop - AgriGuard Mobile Touch Target Gate

Date: 2026-07-06

## Source basis

- AutoResearch/Karpathy source guard refreshed against `https://github.com/Veritas-7/autoresearch-skill-system.git` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- W3C WCAG 2.2 Success Criterion 2.5.8 sets the Level AA target-size floor at 24 by 24 CSS pixels, with defined exceptions: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- W3C WCAG 2.2 Success Criterion 2.5.5 documents the stricter 44 by 44 CSS pixel target-size criterion used here as the AgriGuard mobile launch gate: https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html

## Baseline finding

The mobile browser probe found visible first-viewport controls below the 44px launch bar:

- menu button at 36px
- shared inputs at 36-40px
- custom selects at 36-40px
- Product Registry mobile form controls below 44px
- toast close button at 24px

Checkbox/radio inputs are treated through their enclosing label target when the label row is the actual tap target.

## Adopted changes

- Raised shared `Button` default, small, large, and icon sizes to at least 44px high/wide.
- Raised shared `Input` height to 44px.
- Added `min-h-11` to remaining route-specific input/select targets.
- Compacted Product Registry mobile spacing so enlarged targets do not push the primary CTA below the first mobile viewport.
- Raised the toast close affordance to an accessible 44px target and replaced the mojibake close label with `Close notification`.
- Added `undersizedTouchTargets` measurement to `nav_browser_smoke.py`.
- Added mobile route checks named `{route}_mobile_touch_targets` when the smoke runs in mobile mode.
- Updated backend smoke tests to cover the new mobile target helper.
- Filtered browser `ERR_ABORTED` entries from dashboard auth smoke's actionable request-failure gate while preserving raw request-failure evidence.

## Evidence

- `npm run test -- ProductRegistry.test.jsx SupplyChain.test.jsx QRTokenManager.test.jsx SensorDeviceManager.test.jsx Dashboard.test.jsx QRReader.test.jsx`: 6 files passed, 50 tests.
- `npm run test -- ProductRegistry.test.jsx Dashboard.test.jsx`: 2 files passed, 6 tests.
- `npm run build:lts`: passed.
- `python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5197 --operator-token browser-smoke-token --click-nav --json-out var\agriguard-nav-mobile-touch-targets-2026-07-06.json --screenshot-dir var\agriguard-nav-mobile-touch-targets-2026-07-06 --timeout-ms 30000 --mobile`: 65/65 PASS.
- `python apps\AgriGuard\scripts\dashboard_auth_browser_smoke.py --base-url http://127.0.0.1:5197 --operator-token browser-smoke-token --json-out var\agriguard-dashboard-auth-touch-targets-2026-07-06.json --screenshot var\agriguard-dashboard-auth-touch-targets-2026-07-06.png --timeout-ms 30000`: 14/14 PASS.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5197 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-touch-targets-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-touch-targets-2026-07-06 --timeout-ms 30000 --include-unavailable-check`: 7/7 steps passed, 166/166 checks passed, 19/19 screenshots passed.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5197 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-touch-targets-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-touch-targets-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`: 7/7 steps passed, 180/180 checks passed, 19/19 screenshots passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`: passed=5, failed=0, total=5.
- `python ops\scripts\run_workspace_smoke.py --scope workspace`: passed=9, failed=0, total=9.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-touch-targets-2026-07-06.json`: status `blocked`, blocker_class `preflight_blocked`.

## Remaining blocker

Launch is still externally blocked on operator-provided Firebase Admin credentials:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

The current ready gate remains correct: env validation passes, artifacts and consumer command metadata pass, and guarded launch should not proceed until the operator supplies a real service-account file outside the repository and reruns strict preflight.
