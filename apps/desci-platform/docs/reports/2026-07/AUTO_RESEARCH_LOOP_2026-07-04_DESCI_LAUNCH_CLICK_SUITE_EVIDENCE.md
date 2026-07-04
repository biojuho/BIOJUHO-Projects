# AutoResearch Loop: DeSci Launch Click Suite Evidence

Date: 2026-07-04
App: DeSci / DecentBio
Cycle: launch-critical browser click coverage

## Objective

Refresh live browser evidence for the launch-critical click suite and pair it with strict product-smoke readiness so launch review can separate UI readiness from external env blockers.

## A/B Contract

- Baseline: the latest full browser artifact passed 57 checks, but did not mark the run as the explicit launch-click preset.
- Variant: run `browser_smoke.py --launch-click-suite` with dev-auth, screenshots, and failure traces enabled.
- Decision rule: adopt the evidence only if every selected launch-click check passes, no failure traces are emitted, strict product smoke preserves the live blocker contract, and canonical DeSci workspace smoke passes.

## Evidence

- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\desci-browser-smoke-launch-click-suite-20260704.json --screenshot-dir var\desci-browser-smoke-launch-click-suite-20260704-screens --trace-on-failure-dir var\desci-browser-smoke-launch-click-suite-20260704-traces --timeout 30`
  - Result: pass
  - Summary: `total=44`, `passed=44`, `failed=0`
  - Launch preset: `expected_check_count=44`, `executed_check_count=44`, `passed_check_count=44`, `missing_checks=[]`
  - Screenshot artifacts: 44 PNGs recorded
  - Failure traces: none
- `python apps/desci-platform/scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --strict-ready --json-out var\desci-product-smoke-strict-launch-click-suite-20260704.json`
  - Result: expected fail-closed strict readiness
  - Summary: `total=5`, `passed=3`, `failed=2`, `strict_ready=true`
  - Required blockers: `auth`, `stripe`, `cors`
  - Required env: `GOOGLE_APPLICATION_CREDENTIALS`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`, `ALLOWED_ORIGINS`
  - Ready/launch action coverage: `status=match`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-launch-click-suite-20260704.json`
  - Result: pass
  - Summary: `passed=8`, `failed=0`, `total=8`

## Decision

Adopt this as current DeSci launch-click evidence. The product UI click paths are green, the repo-level DeSci smoke is green, and public launch remains externally blocked by required auth, Stripe, and CORS runtime configuration.
