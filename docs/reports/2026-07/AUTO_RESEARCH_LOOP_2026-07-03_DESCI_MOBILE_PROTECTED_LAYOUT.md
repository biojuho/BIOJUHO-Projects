# AutoResearch Loop - DSCI Mobile Protected Layout

Date: 2026-07-03
App: `apps/desci-platform`
Branch: `feat/shared-llm-modernization-2026-06-19`

## Source-Backed Radar

- Refreshed `ops/scripts/github_modernization_radar.py --refresh-latest-commits`.
- Output: `github modernization radar valid: 8 sources, adopted=8, partially_adopted=0, watch=0`.
- Report: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_CONTINUATION_2026-07-03.md`.
- Review queue still maps browser smoke and real app evidence to the adopted MCP eval / agent readiness patterns.

## Hypothesis

The protected app shell should reserve stable mobile inset and toolbar dimensions on authenticated routes. The browser audit found the opposite: `/upload`, `/dashboard`, and `/vc-portal` rendered their protected content at the viewport edge, and the mobile menu button collapsed visually.

Baseline observed during the browser audit:

- `main padding-left`: `0px`
- protected content left edge: approximately `1px`
- first shell menu button: `x=1`, `width=21`

## Variant Decision

- Variant A: edit `Layout.jsx` and shared `index.css`.
- Variant B: add a targeted protected-shell CSS import after `index.css`.

Variant B shipped because `Layout.jsx` and `index.css` already had unrelated working-tree edits. The added CSS is isolated to protected mobile shell selectors and keeps the commit away from unrelated wallet/layout theme work.

## Implementation

- Added `frontend/src/protected-mobile-layout.css`.
- Imported it from `frontend/src/main.jsx` after the existing app stylesheet.
- Added browser smoke check `protected-mobile-layout-inset` to measure `/upload` at `390x844`.
- Added source-guard coverage in `backend/tests/test_browser_smoke.py`.

## Browser Evidence

After fix, Chromium mobile metrics:

| Route | Main padding | Content left | H1 left | Menu left | Menu width | Scroll width |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/upload` | `12px` | `12px` | `17.18px` | `13px` | `44px` | `390px` |
| `/dashboard` | `12px` | `12px` | `17.71px` | `13px` | `44px` | `390px` |
| `/vc-portal` | `12px` | `12px` | `18.27px` | `13px` | `44px` | `390px` |

Screenshots:

- `var/desci-screenshots/2026-07-03-mobile-protected-layout-after/mobile-upload.png`
- `var/desci-screenshots/2026-07-03-mobile-protected-layout-after/mobile-dashboard.png`
- `var/desci-screenshots/2026-07-03-mobile-protected-layout-after/mobile-vc-portal.png`

## Verification

Passed:

- `uv run pytest tests/test_browser_smoke.py -q -p no:cacheprovider`
  - `34 passed in 1.64s`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check protected-mobile-layout-inset --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-mobile-layout-auto-research.json`
  - `protected-mobile-layout-inset OK`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check upload-form-readiness --only-check protected-mobile-layout-inset --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-upload-mobile-layout-auto-research.json`
  - `upload-form-readiness OK`
  - `protected-mobile-layout-inset OK`
- `npm run build:lts` from `D:\AI project\apps\desci-platform\frontend`
  - Vite production build passed.

Note: the same build command fails from the junction path `D:\AI project\desci-platform\frontend` because Vite emits the HTML asset as `../../apps/desci-platform/frontend/index.html`. The tracked path build is the valid verification path for this repo.

## Release State

This removes one real mobile launch-readiness regression and pins it with a browser smoke check. It does not change the known external production blockers for auth, Stripe, CORS, RabbitMQ, IPFS, or GROBID credentials/configuration.
