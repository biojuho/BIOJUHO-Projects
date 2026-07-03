# AutoResearch Loop - DeSci Deploy Readiness Owner Surfaces

Date: 2026-07-03
Scope: `apps/desci-platform` external deployment readiness handoff
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue product launch hardening after product smoke began printing launch
next actions. This cycle makes the external deployment preflight group failures
by owner and surface so the remaining launch blockers are actionable across
Railway, Vercel, Firebase, Stripe, GitHub, and Web3 deployment work.

## External Sources Checked

- `karpathy/autoresearch`: latest observed `master`
  `228791fb499afffb54b46200aca536f79142f117`.
- `Veritas-7/autoresearch-skill-system`: latest observed `main`
  `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `lastmile-ai/mcp-eval`: latest observed `main`
  `7c0f4d1072d0deb6a36a178312c83023cdd96b69`.
- `microsoft/playwright-mcp`: latest observed `main`
  `36ec986b8b1fc6b4d11f2b6971147755e1b0bc84`.
- GitHub MCP offline evaluation article: benchmark outputs should identify
  expected arguments and exact missing fields, not only the failed tool.
- Railway FastAPI deployment docs: backend deployment is a distinct service
  setup surface with public networking and deployment configuration.
- Vercel CORS guidance: deployed browser paths need explicit CORS origin
  handling and preflight validation, not wildcard/local assumptions.

## A/B Contract

Baseline:

- `deploy_readiness.py` emitted a flat checklist. It was correct, but operators
  still had to infer which owner or deployment surface should fix each blocker.

Variant:

- Add derived `owner_surface_summary` to JSON evidence.
- Print an `ACTION BY SURFACE` console section for failed and warning checks.
- Keep the existing check ids, statuses, required keys, and remediation text
  unchanged.

Primary KPI:

- A failed deploy-readiness run should directly show whether the next action is
  owned by Firebase, Stripe, Railway backend, Vercel frontend, GitHub secrets,
  CORS, or Web3 deployment.

Guardrails:

- No secret-shaped test fixtures.
- Existing pass/fail behavior remains unchanged.
- Product smoke and browser smoke still cover the live local app path.

## Decision

Adopted. The variant improves release handoff without weakening readiness
criteria. It does not mark the product launch-ready; it makes the remaining
external setup work easier to execute and verify.

## Verification

- `python -m pytest backend/tests/test_deploy_readiness.py`
  - `24 passed`
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py`
  - `44 passed`
- `python scripts/deploy_readiness.py --target railway --target vercel --target github --ignore-process-env --env-file .env.production.example --json-out var/desci-deploy-readiness-owner-surface-2026-07-03.json`
  - exit `1`, expected for example config
  - printed `ACTION BY SURFACE`
  - JSON includes `owner_surface_summary`
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --timeout 10 --strict-ready --json-out var/desci-product-smoke-after-deploy-readiness-owner-surface-2026-07-03.json`
  - exit `1`, expected fail-closed on `auth`, `stripe`, and `cors`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-deploy-readiness-owner-surface-2026-07-03.json`
  - OK

## Remaining Launch Blockers

The product still needs external configuration before a real release:

- Firebase backend service account and Vercel frontend Firebase config.
- Stripe checkout secrets, webhook secret, price ids, and return origin.
- Railway backend CORS allowlist containing deployed Vercel HTTPS origins.
- Railway backend database, queue/cache, and production runtime variables.
- Vercel frontend API base URL and deployed Web3 contract addresses.
- GitHub secret-scanning license/secret configuration.

## Next Cycle

Use the new owner/surface summary to generate a one-command release handoff
packet that aligns `/launch.next_actions`, `product_smoke.py`, and
`deploy_readiness.py` into a single operator checklist.
