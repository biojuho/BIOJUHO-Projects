# AutoResearch Loop - AgriGuard QR Token Clear Label - 2026-07-06

## Scope

Polish the QR Tokens operator-token recovery control after the aggregate mobile browser pass showed it was touch-safe but still icon-only on mobile.

## Change

- `QRTokenManager` now shows a visible `Clear` label beside the clear icon on mobile and desktop.
- The control keeps the `Clear token` accessible name, tooltip, and 44px mobile minimum touch target.
- The compact QR Tokens first-viewport layout remains intact.

## Verification

- `npm.cmd test -- QRTokenManager.test.jsx`: `1` file, `7` tests passed.
- `npx.cmd eslint src/components/QRTokenManager.jsx src/components/QRTokenManager.test.jsx`: passed.
- `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5276 --operator-token browser-smoke-token --mobile --json-out var/agriguard-nav-browser-smoke-qr-token-clear-label.json --screenshot-dir var/agriguard-nav-browser-smoke-qr-token-clear-label-screens --timeout-ms 30000`: `65/65` passed.
- Screenshot checked: `var/agriguard-nav-browser-smoke-qr-token-clear-label-screens/qr_tokens.png`.
- `npm.cmd test -- --run`: `18` files, `101` tests passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-qr-token-clear-label-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_TOKEN_CLEAR_LABEL_2026-07-06.md`: valid, `8` sources, `8` adopted.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
