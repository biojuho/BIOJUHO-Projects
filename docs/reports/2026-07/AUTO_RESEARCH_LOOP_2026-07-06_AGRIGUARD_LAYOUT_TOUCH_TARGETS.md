# AutoResearch Loop - AgriGuard Layout Touch Targets - 2026-07-06

## Scope

Harden desktop and hybrid-device navigation touch targets after desktop nav smoke metrics showed smaller interactive heights that were intentionally not part of the mobile gate.

## Changes

- Desktop top-nav links now use `min-h-11`, matching the existing mobile nav touch target contract.
- The QR Tokens saved-token clear action no longer shrinks at the `sm` breakpoint, so it stays a 44px control across desktop and mobile.
- Layout and QR Tokens unit tests now assert the touch-target classes.

## Verification

- `npm.cmd test -- Layout.test.jsx QRTokenManager.test.jsx`: `2` files, `8` tests passed.
- `npx.cmd eslint src/components/Layout.jsx src/components/Layout.test.jsx src/components/QRTokenManager.jsx src/components/QRTokenManager.test.jsx`: passed.
- Initial desktop nav smoke after the layout change: `var/agriguard-nav-browser-smoke-layout-nav-targets.json`, `54/54` passed; top-nav undersized link count was `0`.
- Final desktop nav smoke after keeping the QR token clear action 44px: `var/agriguard-nav-browser-smoke-layout-nav-targets-rerun.json`, `54/54` passed; every route reported `undersizedTouchTargets: []`.
- Screenshot checked: `var/agriguard-nav-browser-smoke-layout-nav-targets-rerun-screens/qr_tokens.png`.
- `npm.cmd test -- --run`: `18` files, `101` tests passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-layout-touch-targets-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_LAYOUT_TOUCH_TARGETS_2026-07-06.md`: valid, `8` sources, `8` adopted.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
