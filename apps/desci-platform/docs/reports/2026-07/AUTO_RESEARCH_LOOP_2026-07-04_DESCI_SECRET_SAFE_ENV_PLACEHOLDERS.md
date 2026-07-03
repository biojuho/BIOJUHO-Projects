# AutoResearch Loop: DeSci Secret-Safe Env Placeholders

Date: 2026-07-04

## Objective

Remove secret-shaped Stripe placeholders from `.env.production.example` and
make the launch handoff placeholder (`<set-secure-value>`) explicitly fail
closed in DeSci preflight checks.

## A/B Contract

- Baseline: `.env.production.example` used `sk_live_your_key` and
  `whsec_your_secret`, which are not real secrets but match common secret
  scanner patterns.
- Variant: use non-secret-shaped placeholders and teach `env_doctor.py` and
  `deploy_readiness.py` that `<set-secure-value>` remains a placeholder.
- Primary KPI: example env files contain no Stripe secret-shaped placeholders,
  while production example preflight still fails on Stripe.
- Guardrails: env doctor and deploy readiness tests remain green; production
  example remains fail-closed.

## Implementation

- Changed production Stripe example values to `use_secret_manager_not_plaintext`
  and `your_stripe_price_*` placeholders.
- Added `<set-secure-value>` and `set-secure-value` to placeholder fragments in
  both env doctor and deploy readiness.
- Extended tests so copied launch handoff placeholders do not pass Stripe
  readiness checks.

## Verification

- `python -m pytest backend/tests/test_env_doctor.py backend/tests/test_deploy_readiness.py -q`
  - Result: `63 passed in 2.20s`
- `python scripts/env_doctor.py --profile production --ignore-process-env --env-file .env.production.example --json-out var/env-doctor-production-example-placeholder-hardening-2026-07-04.json`
  - Expected fail-closed result: `ok=false`, `11 failed`, `2 warning(s)`.
  - Stripe remained failed.
- `python scripts/deploy_readiness.py --target railway --target vercel --target amoy --target github --ignore-process-env --env-file .env.production.example --json-out var/deploy-readiness-production-example-placeholder-hardening-2026-07-04.json`
  - Expected fail-closed result: `ok=false`, `13 failed`, `3 warning(s)`.
  - `railway_stripe` remained failed.
- `rg -n "(sk_live_|sk_test_|whsec_|rk_live_|rk_test_)" .env.production.example .env.example`
  - Result: no matches.

## Decision

Adopted. The example env file no longer carries secret-shaped Stripe strings,
and copied launch placeholders are still rejected by both production preflight
paths until real operator-owned values are installed.
