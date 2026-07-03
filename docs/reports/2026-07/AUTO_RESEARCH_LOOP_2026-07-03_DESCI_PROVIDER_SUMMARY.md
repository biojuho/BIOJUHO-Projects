# AutoResearch Loop - DeSci Provider Summary

Date: 2026-07-03
App: apps/desci-platform
Branch: feat/shared-llm-modernization-2026-06-19

## Objective

Make the DeSci launch handoff easier to execute by surfacing unresolved release work by deployment provider, not only as separate env template files.

## Source Basis

- Railway variables: service variables and raw env import are the correct target for backend runtime configuration.
- Vercel environment variables: frontend deployment values are configured outside source code and applied by environment.
- GitHub Actions secrets: repository secrets can be added through the UI or `gh secret set`.
- AutoResearch pattern: keep each loop evidence-backed, validate before publishing, and preserve explicit commit/push gates.

Sources checked:

- https://docs.railway.com/variables
- https://vercel.com/docs/environment-variables
- https://docs.github.com/actions/security-guides/using-secrets-in-github-actions
- https://github.com/karpathy/autoresearch
- https://github.com/lastmile-ai/mcp-eval
- https://github.com/Veritas-7/autoresearch-skill-system

## A/B Decision

- A: Keep provider-specific env files only. Operators still need to open every generated file or infer ownership from the product checklist.
- B: Add a structured `provider_summary` to the JSON payload and a `## Provider Summary` section to Markdown, while keeping provider env files unchanged.

Selected B because it preserves the previous artifact split and adds a reviewable, machine-readable owner summary.

## Changes

- Added `provider_summary` to `scripts/release_handoff.py`.
- Grouped unresolved product-mapped and deploy-only actions by provider.
- Included provider label, template filename, action count, fail/warn counts, deduped env keys, and action metadata.
- Added a Markdown provider summary section before the full product checklist.
- Extended release handoff tests to verify Railway, Vercel, and GitHub env ownership segregation.

## Generated Evidence

- `apps/desci-platform/var/desci-release-handoff-provider-summary-2026-07-03.json`
- `apps/desci-platform/var/desci-release-handoff-provider-summary-2026-07-03.env`
- `apps/desci-platform/var/desci-release-handoff-provider-summary-2026-07-03.md`
- `apps/desci-platform/var/desci-provider-summary-templates-2026-07-03/railway.env`
- `apps/desci-platform/var/desci-provider-summary-templates-2026-07-03/vercel.env`
- `apps/desci-platform/var/desci-provider-summary-templates-2026-07-03/github.env`
- `apps/desci-platform/var/browser-smoke-provider-summary-2026-07-03.json`
- `var/workspace-smoke-desci-provider-summary-2026-07-03.json`

Observed provider summary from the generated handoff:

- GitHub: 1 action, 1 failed, 0 warnings, template `github.env`
- Railway: 9 actions, 7 failed, 2 warnings, template `railway.env`
- Vercel: 3 actions, 3 failed, 0 warnings, template `vercel.env`

## Verification

- `python -m pytest backend/tests/test_deploy_readiness.py -q` -> 35 passed.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 55 passed.
- `python scripts/release_handoff.py ... --provider-template-dir var/desci-provider-summary-templates-2026-07-03` -> no-go handoff generated, exit 1 normalized as expected for blocked release evidence.
- Secret pattern scan across provider summary templates and Markdown/env artifacts -> no matches.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-provider-summary-2026-07-03.json` -> OK.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-summary-2026-07-03.json` -> 8/8 passed.

## Current Launch State

Local implementation and verification are green, but production launch remains no-go until external provider configuration is completed:

- Railway backend secrets/runtime: Firebase service account, Stripe keys/prices/webhook secret, frontend return URL, CORS origin, Redis/RabbitMQ, Pinata/IPFS, GROBID URL, Postgres `DATABASE_URL`, and `ENV=production`.
- Vercel frontend variables: API base URL, wallet chain id, and deployed contract addresses.
- GitHub repository secret: `GITLEAKS_LICENSE`.
