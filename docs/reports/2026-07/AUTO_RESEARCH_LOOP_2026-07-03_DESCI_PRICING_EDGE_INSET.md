# AutoResearch Loop - DSCI Pricing Edge Inset

Date: 2026-07-03
App: `apps/desci-platform`
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch hardening with source-backed AutoResearch, direct browser inspection, A/B adoption, and commit/push evidence. This cycle focused on the public pricing page because it is a purchase-conversion surface.

## External And Workspace Evidence

- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - observed `b8bbf393759d6e67e780f03c572ec626fab6593b`
- `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-next.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_NEXT_2026-07-03.md`
  - `github modernization radar valid: 8 sources, adopted=8, partially_adopted=0, watch=0`
- Existing DeSci product smoke and browser smoke passed before this change, which showed the previous smoke coverage missed visual edge-inset regressions.

## Baseline

Direct Playwright screenshot and DOM geometry audit found pricing content pinned to the viewport edge:

| Viewport | Metric | Baseline |
| --- | --- | ---: |
| Mobile 390px | `h1.left` | `0px` |
| Mobile 390px | `grid.left` | `0px` |
| Mobile 390px | first card left | `0px` |
| Mobile 390px | pricing CTA height | `22px` |
| Desktop 1440px | first card left | `0px` |
| Desktop 1440px | dashboard nav CTA right | `1440px` |
| Desktop 1440px | pricing CTA height | `22px` |

Screenshots before adoption:

- `var/desci-screenshots/2026-07-03-next-audit/mobile-pricing.png`
- `var/desci-screenshots/2026-07-03-next-audit/desktop-pricing.png`

## A/B Decision

- Variant A: repair global `index.css` utility behavior.
- Variant B: add pricing-specific stable class markers and a small imported pricing layout safety layer.

Variant B was adopted. The worktree has unrelated edits in global CSS and many DeSci frontend files, so a pricing-specific layer fixed the public conversion surface without claiming ownership of unrelated style changes.

Primary KPI: pricing page visible content keeps at least a 12px viewport inset and CTAs meet a 44px touch target.

Guardrails: no pricing browser action regression, PricingPage tests pass, production build passes, DeSci workspace smoke passes.

## Implementation

- Added `frontend/src/pricing-layout.css`.
- Imported it from `frontend/src/main.jsx`.
- Added stable pricing shell/container/grid class markers in `PricingPage.jsx`.
- Added browser smoke check `pricing-layout-inset` for mobile `390x844` and desktop `1440x900`.
- Added source-guard test coverage in `backend/tests/test_browser_smoke.py`.

## Variant Evidence

After adoption:

| Viewport | Metric | Variant |
| --- | --- | ---: |
| Mobile 390px | `h1.left` | `12px` |
| Mobile 390px | `grid.left` | `12px` |
| Mobile 390px | first card left | `12px` |
| Mobile 390px | pricing CTA height | `48px` |
| Desktop 1440px | first card left | `123.19px` |
| Desktop 1440px | dashboard nav CTA right | `1392px` |
| Desktop 1440px | pricing CTA height | `48px` |

Screenshots after adoption:

- `var/desci-screenshots/2026-07-03-pricing-layout-after/mobile-pricing.png`
- `var/desci-screenshots/2026-07-03-pricing-layout-after/desktop-pricing.png`

## Verification

Passed:

- `python apps/desci-platform/scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --json-out var/desci-product-smoke-auto-research-next.json`
  - API, health, ready, launch, and frontend checks passed; launch remained `decision=no-go` from known external readiness blockers.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --trace-on-failure-dir var/desci-browser-traces --json-out var/desci-browser-smoke-auto-research-next.json`
  - full browser smoke passed before the visual fix.
- `uv run pytest tests/test_browser_smoke.py -q -p no:cacheprovider`
  - `35 passed in 1.62s`
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check pricing-layout-inset --trace-on-failure-dir var/desci-browser-traces --json-out var/desci-browser-smoke-pricing-layout-auto-research.json`
  - `pricing-layout-inset OK`
- `npm test -- PricingPage`
  - `2 passed`, `5 tests passed`
- `npm run build:lts`
  - Vite production build passed.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check pricing --only-check pricing-enterprise-contact-intent --only-check pricing-layout-inset --only-check pricing-checkout-mocked --only-check pricing-checkout-yearly --only-check pricing-checkout-cancelled --only-check pricing-checkout-error-visible --only-check pricing-billing-portal --only-check pricing-billing-portal-error-visible --trace-on-failure-dir var/desci-browser-traces --json-out var/desci-browser-smoke-pricing-auto-research-next.json`
  - all pricing route/action checks passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-pricing-layout-auto-research.json`
  - `passed=8, failed=0, total=8`

Note: the first `desci` smoke attempt used a 184-second command timeout and was interrupted. The same command completed successfully with a longer timeout in `3m27s`.

## Release State

Accepted variant B. This improves a public purchase page and adds browser evidence for a visual regression class that the previous route/text smoke did not catch. External production blockers for auth, Stripe, CORS, RabbitMQ, IPFS, and GROBID remain unchanged.
