# AutoResearch Loop: DeSci Post-DailyNews Launch Evidence Refresh

Date: 2026-07-04
App: DeSci / DecentBio
Cycle: current launch evidence refresh after DailyNews status-gate cleanup

## Objective

Refresh DeSci launch evidence after the DailyNews status-gate handoff work, using the existing live local backend/frontend services.

## Evidence

- `python apps\desci-platform\scripts\product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --strict-ready --json-out var\desci-product-smoke-strict-current-20260704-post-dailynews.json`
  - Result: expected strict fail-closed.
  - API, health, ready, launch, and frontend endpoints responded with HTTP 200.
  - Required launch blockers: `auth`, `stripe`, `cors`.
  - Required env remains: `GOOGLE_APPLICATION_CREDENTIALS`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`, `ALLOWED_ORIGINS`.

- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\desci-browser-smoke-launch-click-suite-current-20260704-post-dailynews.json --screenshot-dir var\desci-browser-smoke-launch-click-suite-current-20260704-post-dailynews-screens --trace-on-failure-dir var\desci-browser-smoke-launch-click-suite-current-20260704-post-dailynews-traces --timeout 30`
  - Result: pass.
  - Launch-click suite: `44/44` checks passed.
  - Screenshots recorded for passed checks.
  - Failure trace directory emitted no failure traces.

- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-current-20260704-post-dailynews.json`
  - Result: `passed=8`, `failed=0`, `total=8`.
  - Covered frontend lint, frontend unit tests, frontend build, bundle budget, contracts compile/tests, backend smoke, and release readiness contracts.

## Decision

Adopt this as the current DeSci launch evidence snapshot. The local UI and repo-level gates are green. Public launch remains blocked by external runtime configuration for auth, Stripe, and production CORS, matching the expected strict product-smoke contract.
