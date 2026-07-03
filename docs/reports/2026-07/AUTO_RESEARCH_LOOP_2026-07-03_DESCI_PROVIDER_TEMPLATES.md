# AutoResearch Loop - DeSci Provider-Split Release Templates (2026-07-03)

## Objective

Make the DeSci launch handoff more directly actionable for the people filling external provider configuration by splitting unresolved keys into provider-specific no-secret templates.

## External Basis

Current provider documentation supports provider-specific environment or secret workflows:

- Railway variables are managed at the project/service provider layer.
- Vercel environment variables can be managed by environment and CLI workflows.
- GitHub repository secrets can be managed through Actions secrets and `gh secret set`.

Observed source commits:

- `karpathy/autoresearch`: `228791fb499afffb54b46200aca536f79142f117`
- `lastmile-ai/mcp-eval`: `7c0f4d1072d0deb6a36a178312c83023cdd96b69`
- `Veritas-7/autoresearch-skill-system`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Sources checked:

- https://docs.railway.com/variables
- https://vercel.com/docs/environment-variables
- https://vercel.com/docs/cli/env
- https://docs.github.com/actions/security-guides/using-secrets-in-github-actions
- https://cli.github.com/manual/gh_secret_set
- https://github.com/karpathy/autoresearch
- https://github.com/lastmile-ai/mcp-eval
- https://github.com/Veritas-7/autoresearch-skill-system

## A/B Decision

A. Keep one combined no-secret env template.

- Benefit: simple single artifact.
- Weakness: Railway, Vercel, and GitHub owners still need to manually filter their own keys.

B. Add provider-specific no-secret templates while preserving the combined env template.

- Benefit: produces `railway.env`, `vercel.env`, and `github.env` with only the unresolved keys for that provider target.
- Weakness: adds one more CLI output mode and tests.

Selected B because it reduces operator filtering and better matches provider-specific launch workflows without storing secret values.

## Changes

- Added `--provider-template-dir` to `apps/desci-platform/scripts/release_handoff.py`.
- Added provider grouping helpers:
  - `unresolved_surface_actions()`
  - `provider_actions()`
  - `render_provider_env_template()`
  - `write_provider_templates()`
- Provider outputs currently use no-secret blank values:
  - `railway.env`
  - `vercel.env`
  - `github.env`
  - `amoy.env` or `product.env` if future evidence needs them.
- Added regression tests for provider split behavior and CLI output.

## Evidence

- `python -m pytest backend/tests/test_deploy_readiness.py -q`
  - Result: `35 passed`.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q`
  - Result: `55 passed`.
- `python scripts/release_handoff.py --product-smoke-json var/desci-product-smoke-ipfs-grobid-coverage-2026-07-03.json --deploy-readiness-json var/desci-deploy-readiness-ipfs-grobid-coverage-2026-07-03.json --json-out var/desci-release-handoff-provider-templates-2026-07-03.json --env-template-out var/desci-release-handoff-provider-templates-2026-07-03.env --markdown-out var/desci-release-handoff-provider-templates-2026-07-03.md --provider-template-dir var/desci-provider-templates-2026-07-03`
  - Result: expected fail-closed `no-go`.
  - Provider templates generated:
    - `apps/desci-platform/var/desci-provider-templates-2026-07-03/railway.env`
    - `apps/desci-platform/var/desci-provider-templates-2026-07-03/vercel.env`
    - `apps/desci-platform/var/desci-provider-templates-2026-07-03/github.env`
- Secret-shaped pattern scan over provider templates, Markdown, and combined env template:
  - Result: no matches for Stripe secret keys, webhook secrets, database URLs, AMQP/Redis URLs, private-key blocks, GitHub tokens, or Firebase API-key-shaped values.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-provider-templates-2026-07-03.json`
  - Result: 2/2 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-templates-2026-07-03.json`
  - Result: 8/8 passed in 2m56s.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-03-provider.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03_PROVIDER.md`
  - Result: radar valid, 8 sources, adopted=8.

## Current Launch State

Local implementation and verification remain green. Launch is still fail-closed on external configuration:

- Railway: auth, Stripe, frontend return URL, CORS, Redis/RabbitMQ, IPFS, GROBID, database, and `ENV=production`.
- Vercel: API base URL and wallet settings.
- GitHub: Gitleaks license secret.

The new provider-specific templates make the remaining work easier to distribute without weakening secret hygiene.
