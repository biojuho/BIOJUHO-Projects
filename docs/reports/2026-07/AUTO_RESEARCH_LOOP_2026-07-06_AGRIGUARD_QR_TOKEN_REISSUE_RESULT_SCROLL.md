# AutoResearch Loop: AgriGuard QR Token Reissue Result Scroll

- Date: 2026-07-06
- Scope: AgriGuard launch polish, operator QR token workflow
- Loop input: continue source-backed AutoResearch improvement after the mobile dashboard trend fix, inspect the latest browser screenshots, choose the highest-value visible issue, verify, commit, and push.

## Source-Backed Pattern

- Current AutoResearch/SelfEvolve source baseline remains `Veritas-7/autoresearch-skill-system` at observed `main`/`HEAD` `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Browser-automation comparison sources remained the MCP/browser projects checked in the prior loop:
  - `https://github.com/Uninen/devserver-mcp`
  - `https://github.com/hummer98/e2e-mcp-server`
  - `https://github.com/kontext-security/browser-use-mcp-server`
- Adopted pattern for this iteration: do not rely only on green route checks; inspect the generated mobile screenshots and fix user-facing workflow visibility issues.

## A/B Decision

- Baseline A: after `Reissue label`, render the one-time label URL card but leave the viewport wherever the modal/action flow ended.
  - Browser smoke passed, but the authenticated QR-token screenshot showed the success result starting under the fixed mobile nav, partially hiding the preceding success context.
  - Baseline artifact: `var/agriguard-browser-smoke-suite-mobile-trend-2026-07-06/admin-routes-screens/qr-tokens.png`.
- Variant B: when a one-time QR label URL appears, scroll the result card into view and reserve fixed-nav space with `scroll-mt-24`.
  - The URL card starts below the fixed nav in the post-fix screenshot.
  - Component test asserts the success card has the scroll margin and calls `scrollIntoView({ block: 'start', behavior: 'auto' })`.
- Decision: ship Variant B. The one-time label URL is the critical artifact of the reissue flow, so it should be brought into view deterministically.

## Changed Files

- `apps/AgriGuard/frontend/src/components/QRTokenManager.jsx`
  - Added a result-card ref.
  - Scrolls the result card into view when `actionState.success.qrCode` appears.
  - Adds `scroll-mt-24` to keep the result clear of the fixed mobile nav.
- `apps/AgriGuard/frontend/src/components/QRTokenManager.test.jsx`
  - Mocks `scrollIntoView`.
  - Verifies the reissue result card is scroll-targeted and has the fixed-nav offset class.

## Verification

- `npm run test -- QRTokenManager.test.jsx`
  - Passed: `1` file, `7` tests.
- `npm run build:lts`
  - Passed: production frontend build.
- `python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-admin-routes-mobile-reissue-scroll-2026-07-06.json --screenshot-dir var\agriguard-admin-routes-mobile-reissue-scroll-2026-07-06 --timeout-ms 30000 --mobile`
  - Passed.
  - Post-fix artifact: `var/agriguard-admin-routes-mobile-reissue-scroll-2026-07-06/qr-tokens.png`.
- `npm run lint`
  - Passed with existing warning: `react-refresh/only-export-components` in `Dashboard.jsx`.
- `npm run test`
  - Passed: `15` files, `83` tests.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-reissue-scroll-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-reissue-scroll-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Passed: `7/7` steps, `166/166` checks, `19/19` screenshots.
  - Post-fix suite artifact: `var/agriguard-browser-smoke-suite-reissue-scroll-2026-07-06/admin-routes-screens/qr-tokens.png`.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Passed: `5/5` checks.
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Passed: `9/9` checks.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-reissue-scroll-2026-07-06.json`
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Operator action: `set_firebase_service_account_file`
  - Blocking preflight error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Current Launch State

The QR-token reissue path now exposes its one-time URL result clearly on mobile and all local verification for this iteration is green. Production compose launch remains intentionally blocked until the operator provides a real Firebase Admin service account JSON outside the repository and reruns strict preflight.
