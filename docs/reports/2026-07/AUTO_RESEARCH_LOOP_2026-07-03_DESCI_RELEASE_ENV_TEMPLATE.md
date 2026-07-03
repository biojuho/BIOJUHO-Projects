# AutoResearch Loop - DeSci Release Env Template (2026-07-03)

## Objective

Turn the release handoff no-go state into a no-secret operator `.env` template so external blockers can be filled without copying real secret values into repo artifacts.

## A/B Decision

A. Keep only JSON and console handoff output.

- Benefit: already machine-readable.
- Weakness: operators still need to manually extract every missing key across product and deploy-only blockers.

B. Add `--env-template-out` to `scripts/release_handoff.py`.

- Benefit: generates grouped, blank `KEY=` lines from unresolved failed/warn surfaces.
- Weakness: one more output mode to test.

Selected B because it converts the remaining external launch blockers into a directly actionable provider/secret-manager checklist without storing values.

## Changes

- Added `render_env_template()` and `write_env_template()` to `scripts/release_handoff.py`.
- Added `--env-template-out` CLI support.
- Made `_string_list()` accept tuples as well as lists so direct in-process test payloads match JSON-roundtripped payloads.
- Added a regression test that verifies:
  - unresolved keys are emitted,
  - pass-only surfaces are skipped,
  - fixture secret-like values are not emitted,
  - duplicate keys are not repeated.

## Evidence

- `python -m pytest backend/tests/test_deploy_readiness.py -q`
  - Result: `31 passed`.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q`
  - Result: `51 passed`.
- `python scripts/release_handoff.py --product-smoke-json var/desci-product-smoke-ipfs-grobid-coverage-2026-07-03.json --deploy-readiness-json var/desci-deploy-readiness-ipfs-grobid-coverage-2026-07-03.json --json-out var/desci-release-handoff-env-template-2026-07-03.json --env-template-out var/desci-release-handoff-unresolved-2026-07-03.env`
  - Result: expected fail-closed `no-go`.
  - Env template evidence: `apps/desci-platform/var/desci-release-handoff-unresolved-2026-07-03.env`.
- Secret-shaped pattern scan over the generated env template:
  - Result: no matches for Stripe secret keys, webhook secrets, database URLs, AMQP/Redis URLs, private-key blocks, or GitHub tokens.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-env-template-2026-07-03.json`
  - Result: 2/2 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-env-template-2026-07-03.json`
  - Result: 8/8 passed in 3m5s.

## Current No-Go State

The remaining launch blocker is still external configuration and secrets, not local code regression. The generated template now lists blank keys for Firebase, Stripe, return URLs, CORS, Redis/RabbitMQ, Pinata, GROBID, GitHub Gitleaks, database, production profile, Vercel API base, and wallet deployment settings.
