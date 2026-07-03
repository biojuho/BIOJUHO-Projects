# AutoResearch Loop: DeSci Launch Env Handoff

Date: 2026-07-04

## Objective

Reduce the remaining DeSci launch blocker handoff gap. The app click path is
working, but strict product smoke still blocks release on external production
configuration values.

## Sources Checked

- Twelve-Factor App config guidance:
  `https://12factor.net/config`
- Stripe API key documentation:
  `https://docs.stripe.com/keys`
- Stripe secret-key best practices:
  `https://docs.stripe.com/keys-best-practices`
- Firebase Admin SDK setup:
  `https://firebase.google.com/docs/admin/setup`
- Google Application Default Credentials:
  `https://docs.cloud.google.com/docs/authentication/application-default-credentials`
- Veritas AutoResearch source HEAD:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

External pattern adopted: environment configuration should remain outside code
and secret values must not appear in generated diagnostics. The local variant
therefore emits only env key names and placeholders.

## A/B Contract

- Baseline: `product_smoke.py --strict-ready` reports `auth`, `stripe`, and
  `cors` blockers and prints next actions, but its JSON has no copy-ready env
  handoff grouping.
- Variant: add top-level `launch_env_handoff` to the product smoke JSON with
  required env keys, optional env keys, action IDs, a placeholder-only copy
  block, and an explicit `secret_policy`.
- Primary KPI: launch artifact exposes all required release env keys without
  secret-shaped values or raw URLs.
- Guardrails: DeSci canonical smoke remains green, browser launch-click suite
  remains green, and strict product smoke still fails closed while external
  blockers remain unresolved.
- Decision rule: adopt only if the new field is present, contains no secret or
  URL-shaped copy lines, and no relevant smoke/browser guardrail regresses.

## Implementation

- Added `launch_env_handoff_report()` in
  `apps/desci-platform/scripts/product_smoke.py`.
- Added focused tests in
  `apps/desci-platform/backend/tests/test_product_smoke_launch_env_handoff.py`.

The new JSON field is intentionally separate from `launch_handoff`, preserving
existing release-gate consumers while giving operators a safer copy-ready
checklist.

## Verification

- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke_launch_env_handoff.py -q`
  - Result: `2 passed in 0.49s`
- `python apps/desci-platform/scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --strict-ready --json-out apps/desci-platform/var/product-smoke-launch-env-handoff-2026-07-04.json`
  - Expected fail-closed result: `ready` blocked and `launch` no-go on
    `auth`, `stripe`, `cors`.
  - New handoff result:
    - `status=blocked`
    - required env:
      `GOOGLE_APPLICATION_CREDENTIALS`, `FIREBASE_SERVICE_ACCOUNT_JSON`,
      `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
      `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`,
      `ALLOWED_ORIGINS`
    - optional env:
      `RABBITMQ_URL`, `PINATA_JWT`, `PINATA_API_KEY`,
      `PINATA_API_SECRET`, `GROBID_ENABLED`, `GROBID_URL`
    - `operator_copy_lines=17`
    - `bad_lines=[]`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-launch-env-handoff-2026-07-04.json`
  - Result: `8/8 passed`
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out apps/desci-platform/var/browser-smoke-launch-env-handoff-2026-07-04.json --trace-on-failure-dir apps/desci-platform/var/browser-smoke-launch-env-handoff-2026-07-04-traces`
  - Result: `9/9 launch click checks OK`

## Decision

Adopted. The variant improves operator handoff quality without changing the
fail-closed launch decision. Production release remains blocked until the real
auth, Stripe, and CORS values are configured and strict product smoke returns
ready/go.
