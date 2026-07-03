# AutoResearch Loop - DeSci Markdown Release Handoff (2026-07-03)

## Objective

Make the DeSci no-go launch state easier to share in release review by adding a human-readable Markdown handoff packet alongside the existing JSON and no-secret env template outputs.

## External Basis

- Karpathy AutoResearch keeps a measurable keep-or-reject loop for local improvements.
- `lastmile-ai/mcp-eval` keeps machine-readable evidence plus human-readable reports for tool and agent evaluation.
- GitHub MCP evaluation guidance emphasizes explicit expected actions and argument-quality checks instead of vague subjective progress.

Observed source commits:

- `karpathy/autoresearch`: `228791fb499afffb54b46200aca536f79142f117`
- `lastmile-ai/mcp-eval`: `7c0f4d1072d0deb6a36a178312c83023cdd96b69`
- `Veritas-7/autoresearch-skill-system`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Sources checked:

- https://github.com/karpathy/autoresearch
- https://github.com/lastmile-ai/mcp-eval
- https://github.blog/ai-and-ml/generative-ai/measuring-what-matters-how-offline-evaluation-of-github-mcp-server-works/
- https://github.com/Veritas-7/autoresearch-skill-system

## A/B Decision

A. Keep release handoff as console, JSON, and no-secret env template only.

- Benefit: already machine-readable and directly usable for deployment variables.
- Weakness: release review still requires reading JSON or console logs.

B. Add a Markdown release handoff packet.

- Benefit: one artifact can be pasted into release review, issue comments, or operator handoff without exposing secret values.
- Weakness: another output mode requires contract tests.

Selected B. It improves the real handoff path without weakening the fail-closed release decision.

## Changes

- Added `--markdown-out` to `apps/desci-platform/scripts/release_handoff.py`.
- Added `render_markdown_report()` and `write_markdown_report()`.
- Reused one atomic text writer for Markdown and env template outputs.
- Normalized Markdown scalar values to `true`/`false` instead of Python `True`/`False`.
- Added release handoff tests for Markdown rendering and CLI output.

## Evidence

- `python -m pytest backend/tests/test_deploy_readiness.py -q`
  - Result: `33 passed`.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q`
  - Result: `53 passed`.
- `python scripts/release_handoff.py --product-smoke-json var/desci-product-smoke-ipfs-grobid-coverage-2026-07-03.json --deploy-readiness-json var/desci-deploy-readiness-ipfs-grobid-coverage-2026-07-03.json --json-out var/desci-release-handoff-markdown-2026-07-03.json --env-template-out var/desci-release-handoff-markdown-2026-07-03.env --markdown-out var/desci-release-handoff-markdown-2026-07-03.md`
  - Result: expected fail-closed `no-go`.
  - Markdown evidence: `apps/desci-platform/var/desci-release-handoff-markdown-2026-07-03.md`.
- Secret-shaped pattern scan over the Markdown and env template:
  - Result: no matches for Stripe secret keys, webhook secrets, database URLs, AMQP/Redis URLs, private-key blocks, GitHub tokens, or Firebase API-key-shaped values.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-markdown-handoff-2026-07-03.json`
  - Result: 2/2 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-markdown-handoff-2026-07-03.json`
  - Result: 8/8 passed in 2m29s.
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-03-continue.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03_CONTINUE.md`
  - Result: radar valid, 8 sources, adopted=8.

## Current Launch State

Local implementation and verification are green. Launch remains fail-closed on external/operator configuration:

- Required product blockers: `auth`, `stripe`, `cors`.
- Optional warnings are covered by deploy surfaces: `rabbitmq`, `ipfs`, `grobid`.
- Deploy-only external blockers remain for GitHub Gitleaks, database, production env, Vercel API base, Vercel wallet contracts, and wallet chain id.

The new Markdown packet makes that state reviewable without reading raw JSON or exposing secret values.
