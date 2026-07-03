# AutoResearch Loop - DSCI Public Touch Targets

Date: 2026-07-03
App: `apps/desci-platform`
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue product launch hardening with source-backed AutoResearch, direct browser inspection, A/B adoption, and commit/push evidence. This cycle focused on public mobile surfaces because they are first-contact conversion paths.

## External And Workspace Evidence

- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - observed `b8bbf393759d6e67e780f03c572ec626fab6593b`
- `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-loop.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_LOOP_2026-07-03.md`
  - `github modernization radar valid: 8 sources, adopted=8, partially_adopted=0, watch=0`
- External pattern used: GitHub-backed browser/tool evaluation and dev-server validation patterns from the workspace radar sources.

## Baseline

Direct Playwright mobile audit at `390x844` found visible controls below a usable touch target on public pages:

| Route | Baseline examples |
| --- | --- |
| `/` | Locale buttons `20x16`, sign-in `40.64x22`, primary CTA `93.2x22`, hero CTAs `26px` high |
| `/explore` | Locale buttons `~20x16`, header CTA `77.5x22`, search input `26px` high, field pills `16-18px` high |
| `/investors` | select filters `26px` high |
| `/pricing` | Locale buttons `~39x32`, dashboard CTA `38px` high |

The existing route and action smoke checks passed, so this was a visual/interaction target gap rather than a route availability failure.

## A/B Decision

- Variant A: patch each public component individually.
- Variant B: add a shared touch-target CSS layer and stable LocaleToggle class markers.

Variant B was adopted because the defect crossed public pages and shared design primitives. It avoids editing the dirty global `index.css` while preserving a narrow ownership surface.

Primary KPI: all visible audited public controls on mobile are at least `44px` wide and `44px` high.

Guardrails: no horizontal overflow, public browser actions still pass, frontend tests/build pass, DeSci workspace smoke passes.

## Implementation

- Added `frontend/src/touch-targets.css`.
- Imported it from `frontend/src/main.jsx` after existing layout layers.
- Added `locale-toggle` and `locale-toggle-button` class markers in `LocaleToggle.jsx`.
- Added browser smoke check `public-touch-targets` for `/`, `/explore`, `/investors`, and `/pricing`.
- Added source-guard coverage in `backend/tests/test_browser_smoke.py`.

## Variant Evidence

After adoption, mobile `390x844` audit showed `tooSmall: []` and `scrollWidth: 390` for all audited public routes:

| Route | Sample variant metrics |
| --- | --- |
| `/` | KO `44x44`, EN `44x44`, sign-in `60x62`, primary CTA `106.23x62`, hero CTAs `46px` high |
| `/explore` | DSCI `95.02x44`, KO `44.63x44`, EN `44x44`, search input `390x46`, field pills `>=44px` high |
| `/investors` | country select `388x46`, stage select `388x46` |
| `/pricing` | back link `62.64x44`, KO `44x44`, EN `44x44`, dashboard CTA `98.3x44` |

Screenshots after adoption:

- `var/desci-screenshots/2026-07-03-public-touch-targets-after/mobile-home.png`
- `var/desci-screenshots/2026-07-03-public-touch-targets-after/mobile-explore.png`
- `var/desci-screenshots/2026-07-03-public-touch-targets-after/mobile-investors.png`
- `var/desci-screenshots/2026-07-03-public-touch-targets-after/mobile-pricing.png`

## Verification

Passed:

- `python apps/desci-platform/scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --json-out var/desci-product-smoke-auto-research-loop.json`
  - API, health, ready, launch, and frontend checks passed; launch remained `decision=no-go` from known external readiness blockers.
- `uv run pytest tests/test_browser_smoke.py -q -p no:cacheprovider`
  - `36 passed in 2.28s`
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check public-touch-targets --trace-on-failure-dir var/desci-browser-traces --json-out var/desci-browser-smoke-public-touch-targets-auto-research.json`
  - `public-touch-targets OK`
- `npm test -- LandingPage ResearchFeed Investors PricingPage`
  - `5 files passed`, `20 tests passed`
- `npm run build:lts`
  - Vite production build passed.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check home --only-check explore --only-check investors --only-check pricing --only-check landing-cta-intent --only-check explore-analyze-intent --only-check investors-filter-directory --only-check pricing-layout-inset --only-check public-touch-targets --trace-on-failure-dir var/desci-browser-traces --json-out var/desci-browser-smoke-public-touch-targets-suite.json`
  - public route/action/touch-target suite passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-public-touch-targets-auto-research.json`
  - `passed=8, failed=0, total=8`

## Next Candidate

The browser audit also showed the public investor directory can still render a confusing empty/placeholder state under some local API timing conditions. That is a separate data-fallback/retry candidate and was not mixed into this touch-target commit.

## Release State

Accepted variant B. This improves mobile usability on public conversion surfaces and adds a browser smoke guard for a class of regressions that text/route smoke does not catch. External production blockers for auth, Stripe, CORS, RabbitMQ, IPFS, and GROBID remain unchanged.
