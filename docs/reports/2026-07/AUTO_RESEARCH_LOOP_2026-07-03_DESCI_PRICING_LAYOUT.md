# AutoResearch Loop - DeSci Pricing Layout - 2026-07-03

## Summary

- Objective: continue direct app inspection after browser smoke passed.
- Baseline evidence: pricing desktop/mobile screenshots showed the Stripe trust marker, billing toggle, and Pro popular badge visually colliding near the top of the pricing grid.
- Outcome: adopted a layout-flow fix for the pricing controls and Pro badge.
- Generated: `2026-07-03T20:55:00+09:00`

## A/B Finding

### Baseline A: absolute/inline placement

- Screenshot evidence:
  - `var/desci-screenshots/2026-07-03-dashboard-audit/desktop-pricing.png`
  - `var/desci-screenshots/2026-07-03-dashboard-audit/mobile-pricing.png`
- Problem:
  - Trust marker and billing toggle rendered on top of each other.
  - Pro popular badge sat on the card border and was partially clipped on mobile.

### Variant B: explicit flow layout

- Changed: `apps/desci-platform/frontend/src/components/PricingPage.jsx`
- Test updated: `apps/desci-platform/frontend/src/__tests__/components/PricingPage.test.jsx`
- Adopted because:
  - Trust marker and billing toggle now occupy separate centered rows.
  - Billing toggle uses explicit control styling so the running dev server and production build render the same spacing.
  - Pro popular badge is inside normal card flow instead of absolute top positioning.

## Verification

- `npm run test:lts -- --run src/__tests__/components/PricingPageLayout.test.jsx src/__tests__/components/PricingPage.test.jsx` -> 5 passed.
- Desktop/mobile screenshot recapture -> console_errors=0.
- Final screenshot evidence:
  - `var/desci-screenshots/2026-07-03-pricing-layout-final/desktop-pricing.png`
  - `var/desci-screenshots/2026-07-03-pricing-layout-final/mobile-pricing.png`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check pricing --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-pricing-layout-auto-research.json` -> passed.
- `npm run build:lts` -> passed.

## Remaining Boundary

- This is a UI layout improvement only.
- Launch status is still controlled by external production auth, Stripe, and CORS configuration.
