# AutoResearch Loop - AgriGuard QR Token Mobile Cards

Date: 2026-07-05

## Objective

Continue launch-readiness hardening for AgriGuard's operator QR label workflow by making loaded QR token rows usable on mobile.

## Source Pattern

- External reference checked this loop: `Veritas-7/autoresearch-skill-system`
- Refreshed upstream commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local skill used: `D:\AI project\.agents\skills\auto-research-karpathy\SKILL.md`

## Baseline

The QR Token Management route passed browser smoke, but the loaded token table still used a desktop-width horizontal layout on mobile.

Baseline evidence:

- Metrics JSON: `var\agriguard-qr-token-mobile-baseline.json`
- Initial screenshot: `var\agriguard-qr-token-mobile-baseline\loaded-qr-tokens-mobile.png`
- Token-row screenshot: `var\agriguard-qr-token-mobile-baseline\loaded-qr-tokens-table-mobile.png`

Observed baseline metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- `tableClass`: `w-full min-w-[760px] border-collapse text-left text-sm`
- `tableWidth`: `760`
- `Revoke` button: `left=767`, `right=833`, `width=66`, `visibleInViewport=false`

This was a launch-readiness issue because operators must be able to revoke compromised QR label tokens from mobile without discovering a horizontal scroll surface.

## A/B Decision

- Variant A: keep the 760px table and rely on horizontal scrolling.
- Variant B: keep one semantic row source but switch small screens to stacked, labeled token rows with full-width actions.

Adopted Variant B.

Implementation details:

- `apps/AgriGuard/frontend/src/components/QRTokenManager.jsx`
  - Replaced unconditional `min-w-[760px]` with `md:min-w-[760px]`.
  - Kept desktop table columns at `md` and above.
  - Rendered each small-screen token row as a stacked bordered row with labels for token, state, batch, scans, last verified, expires, and action.
  - Made `Revoke` full-width on small screens.
- `apps/AgriGuard/frontend/src/components/QRTokenManager.test.jsx`
  - Added a regression test for the mobile-first QR token row layout and visible revoke action.

## Adopted Variant Evidence

Live mobile proof:

- Metrics JSON: `var\agriguard-qr-token-mobile-cards.json`
- Screenshot, row fields: `var\agriguard-qr-token-mobile-cards\loaded-qr-tokens-mobile-actions.png`
- Screenshot, revoke visible: `var\agriguard-qr-token-mobile-cards\loaded-qr-tokens-mobile-revoke-visible.png`

Observed metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- `tableClass`: `w-full border-separate border-spacing-0 text-left text-sm md:min-w-[760px] md:border-collapse`
- `tableWidth`: `244`
- `rowWidth`: `244`
- `Revoke` button: `left=90`, `right=300`, `width=210`, `visibleInViewport=true`

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- QRTokenManager
```

Result:

- `1 passed`
- `6 passed`

Mobile browser suite:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-qr-token-mobile-cards.json --output-dir var\agriguard-browser-smoke-suite-qr-token-mobile-cards --timeout-ms 30000
```

Result:

- `6/6` flows passed
- `135/135` checks passed
- `18/18` screenshot artifacts passed

Canonical AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-token-mobile-cards.json
```

Result:

- `5/5` checks passed
- elapsed `6m5s`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-qr-token-mobile-cards.json
```

Result:

- `9/9` checks passed
- elapsed `2m49s`

## Remaining External Blocker

Local product hardening and verification are green for this loop. Full launch readiness still remains externally blocked on the Firebase Admin service account / operator token environment needed for production-grade protected admin paths.
