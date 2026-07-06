# AutoResearch Loop - AgriGuard Nav Touch Gate - 2026-07-06

## Scope

Make the AgriGuard nav browser smoke enforce first-viewport route affordances and touch-target metrics on every measured viewport, not only mobile-width runs.

## Changes

- `nav_browser_smoke.py` now runs the route affordance and touch-target checks whenever a viewport is measured, including the default `1440x960` desktop pass.
- `test_smoke.py` now locks the desktop behavior so `should_check_mobile_affordances({"viewportWidth": 1440}, mobile=False)` returns `True`.
- The scanner camera frame is bounded to `sm:max-w-[320px]`, keeping the camera usable while pulling the manual verification fallback and `Verify code` CTA fully into the first viewport.
- `QRReader.test.jsx` now asserts the bounded desktop scanner frame class.

## Findings From Initial Strict Run

- First stricter desktop run: `var/agriguard-nav-browser-smoke-nav-touch-gate.json`, `63/65` passed.
- Failed check: `scanner_verify_code_cta_first_viewport`.
- At `1440x960`, the `Verify code` button measured `top=947`, `bottom=991`, `height=44`, `visibleHeight=13`, `visibleRatio=0.295`.
- No desktop route reported undersized touch targets; the real issue was first-viewport scanner layout.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_nav_browser_smoke_tracks_mobile_first_viewport_affordances -q`: `1` passed.
- `python -m py_compile apps/AgriGuard/scripts/nav_browser_smoke.py`: passed.
- `npm.cmd test -- --run QRReader.test.jsx`: `1` file, `17` tests passed.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5279 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-nav-touch-gate.json --screenshot-dir var/agriguard-nav-browser-smoke-nav-touch-gate-screens --timeout-ms 30000`: `65/65` passed.
- Final scanner measurement: `Verify code` button `top=869`, `bottom=913`, `height=44`, `visibleHeight=44`, `visibleRatio=1`, with `undersizedTouchTargets: []`.
- `npm.cmd run lint -- src/components/QRReader.jsx src/components/QRReader.test.jsx`: no errors; existing warning remains in `src/components/dashboard/Dashboard.jsx` for `react-refresh/only-export-components`.
- `npm.cmd test -- --run`: `18` files, `101` tests passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`: `56` passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-nav-touch-gate-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_NAV_TOUCH_GATE_2026-07-06.md`: valid, `8` sources, `8` adopted.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
