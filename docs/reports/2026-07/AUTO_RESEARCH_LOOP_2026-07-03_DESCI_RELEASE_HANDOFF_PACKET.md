# AutoResearch Loop - DeSci Release Handoff Packet (2026-07-03)

## Objective

Make the DeSci launch state easier to operate by combining product smoke `/launch.next_actions` with deploy readiness owner/surface blockers into one fail-closed handoff packet.

## Source Pattern

- Karpathy AutoResearch pattern: keep variants that improve a measurable objective and discard weaker variants.
- `lastmile-ai/mcp-eval`: offline eval reports and regression evidence are useful when operator actions need durable proof.
- GitHub MCP eval writeup: tool-use benchmarks work best when expected tool calls and arguments are evaluated explicitly.

References:

- https://github.com/karpathy/autoresearch
- https://github.com/lastmile-ai/mcp-eval
- https://github.blog/ai-and-ml/generative-ai/measuring-what-matters-how-offline-evaluation-of-github-mcp-server-works/

## A/B Decision

A. Keep `product_smoke.py` and `deploy_readiness.py` evidence separate.

- Benefit: no new code.
- Weakness: operator must manually reconcile product blockers, deploy-only failures, and optional product warnings.

B. Add a release handoff packet that merges both evidence streams.

- Benefit: one command produces product action coverage, deploy surfaces, product-only follow-ups, and deploy-only failures.
- Weakness: adds a mapping contract that needs tests.

Selected B because it reduces handoff ambiguity while preserving the fail-closed launch decision.

## Changes

- Added `scripts/release_handoff.py`.
  - Reads product smoke JSON and deploy readiness JSON.
  - Maps product actions such as `auth`, `stripe`, `cors`, and `rabbitmq` to deploy readiness checks.
  - Keeps optional product-only follow-ups such as `ipfs` and `grobid` visible.
  - Lists deploy-only failed checks such as database, LLM, API base URL, wallet contracts, and repository secret scanning.
  - Writes atomic JSON evidence.
- Extended `backend/tests/test_deploy_readiness.py` with release handoff coverage tests.
- Included the shared `scripts/evidence_io.py` atomic JSON helper that existing DeSci operator scripts import.

## Evidence

- `python -m pytest backend/tests/test_deploy_readiness.py -q`
  - Result: `28 passed`.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q`
  - Result: `48 passed`.
- `python scripts/release_handoff.py --product-smoke-json var/desci-product-smoke-after-deploy-readiness-owner-surface-2026-07-03.json --deploy-readiness-json var/desci-deploy-readiness-owner-surface-2026-07-03.json --json-out var/desci-release-handoff-owner-surface-2026-07-03.json`
  - Result: expected fail-closed `no-go` exit because launch/deploy blockers remain.
  - Evidence: `apps/desci-platform/var/desci-release-handoff-owner-surface-2026-07-03.json`.
  - Product actions: 6 total; covered: `auth`, `stripe`, `cors`, `rabbitmq`; product-only: `ipfs`, `grobid`; missing required coverage: none.
  - Deploy-only actions: 5.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-release-handoff-2026-07-03.json`
  - Result: 2/2 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-release-handoff-2026-07-03.json`
  - Result: 8/8 passed in 2m43s.
  - Evidence: `D:\AI project\var\workspace-smoke-desci-release-handoff-2026-07-03.json`.

## Current No-Go State

Product launch blockers remain external/operator-owned:

- `auth`: Vercel Firebase frontend variables are missing; Railway backend auth check is already passing in the sampled deploy evidence.
- `stripe`: Railway Stripe keys and deployed frontend return URL are missing.
- `cors`: deployed frontend HTTPS origin allowlist is missing.

Deploy-only blockers also remain:

- `github_gitleaks_license`
- `railway_database`
- `railway_llm`
- `vercel_api_base`
- `vercel_wallet_contracts`

Optional product-only follow-ups:

- `ipfs`
- `grobid`

The local implementation and verification path are green; production launch remains blocked on external configuration and secrets.
