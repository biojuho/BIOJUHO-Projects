# AutoResearch Loop: Launch Click Pricing Resilience

Date: 2026-07-04

## Objective

Strengthen DeSci launch-click evidence by covering more monetization recovery
paths in the canonical launch-critical browser preset.

## Scope and Owned Paths

- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

## External Source Check

- `Veritas-7/autoresearch-skill-system` current observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis

- Baseline: `--launch-click-suite` covered 9 critical paths and passed, but it
  included only one paid checkout success path.
- Variant: include pricing yearly checkout, checkout cancellation retry,
  checkout provider error, billing portal success, and billing portal error
  checks in the launch-click preset.
- Decision rule: adopt only if all candidate checks pass individually, the
  expanded launch-click suite passes, no browser console/page errors surface,
  focused tests pass, and canonical DeSci smoke stays green.

## Result

Adopted.

The launch-click preset now covers 14 paths:

- landing CTA intent
- explore analyze intent
- enterprise pricing contact intent
- dashboard quick upload
- dashboard readiness refresh
- pricing checkout monthly success
- pricing checkout yearly success
- pricing checkout cancellation retry
- pricing checkout error visibility
- billing portal success
- billing portal error visibility
- upload form readiness
- upload submit receipt
- asset upload readiness

## Verification

- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var\browser-smoke-launch-click-autoresearch-2026-07-04-continuation.json --screenshot-dir var\browser-smoke-launch-click-autoresearch-2026-07-04-continuation-screens --trace-on-failure-dir var\browser-smoke-launch-click-autoresearch-2026-07-04-continuation-traces` -> baseline 9/9 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --timeout 45 --only-check pricing-checkout-yearly --only-check pricing-checkout-cancelled --only-check pricing-checkout-error-visible --only-check pricing-billing-portal --only-check pricing-billing-portal-error-visible --json-out var\browser-smoke-pricing-launch-candidates-2026-07-04.json --screenshot-dir var\browser-smoke-pricing-launch-candidates-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-pricing-launch-candidates-2026-07-04-traces` -> candidate 5/5 passed.
- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q` -> 47 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var\browser-smoke-launch-click-pricing-resilience-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-pricing-resilience-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-pricing-resilience-2026-07-04-traces` -> expanded 14/14 passed; 14 screenshots captured.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-launch-click-pricing-resilience-2026-07-04.json` -> 8 passed, 0 failed.

## Next Cycle

Continue expanding launch-click coverage into the authenticated research workflow
paths not yet in the preset, prioritizing BioLinker proposal handoff and notices
discovery because those are core product conversion paths after upload.
