# AutoResearch Loop - DeSci Product Smoke Next Actions

Date: 2026-07-03
Scope: `apps/desci-platform` product launch readiness smoke
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch hardening after the pricing/browser smoke guard. This cycle
targets the operator handoff gap in the product smoke CLI: strict launch smoke
failed closed correctly, but the console only showed blocker ids while the JSON
contained the actionable remediations.

## External Sources Checked

- `karpathy/autoresearch`: bounded autonomous loops that keep or discard a
  variant after a measured run. Latest observed `master`:
  `228791fb499afffb54b46200aca536f79142f117`.
- `Veritas-7/autoresearch-skill-system`: local AutoResearch skill source for
  durable archives, A/B adoption rules, and fail-closed audits. Latest observed
  `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `lastmile-ai/mcp-eval`: production-like eval evidence should expose
  actionable traces and assertions instead of mock-only confidence.
- `microsoft/playwright-mcp`: browser automation should use deterministic
  structured checks for agent workflows; local CLI skills remain efficient for
  coding-agent smoke paths.
- GitHub MCP offline evaluation article: short feedback loops and regression
  detection are more useful when the report explains which action failed and
  which arguments or configuration are required.

## A/B Contract

Baseline:

- `product_smoke.py --strict-ready` correctly exited non-zero for `/ready` and
  `/launch`, but console output stopped at `auth`, `stripe`, and `cors` blocker
  ids.

Variant:

- Preserve the JSON evidence contract.
- Add a failure-summary section that prints `/launch.next_actions` with
  required/optional status, remediation, and required environment keys.

Primary KPI:

- The operator can identify the exact required environment keys from the failed
  console run without opening the JSON artifact.

Guardrails:

- No secret-shaped values are introduced.
- Existing JSON evidence remains unchanged except for normal generated fields.
- Product and browser smoke contracts remain green.

## Decision

Adopted. The variant keeps the product fail-closed and improves the handoff from
evidence to action. It does not claim launch readiness; it makes the remaining
external configuration blockers explicit.

## Verification

- `python -m pytest backend/tests/test_product_smoke.py`
  - `20 passed`
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_product_smoke.py`
  - `59 passed`
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --timeout 10 --strict-ready --json-out var/desci-product-smoke-strict-ready-next-actions-2026-07-03.json`
  - exit `1`, expected fail-closed
  - printed next actions for `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, and
    `grobid`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-product-readiness-next-actions-2026-07-03.json`
  - OK
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-product-smoke-next-actions-2026-07-03.json`
  - `passed=8`, `failed=0`, `total=8`

## Remaining Launch Blockers

The local app/browser path is green, but strict launch readiness remains
blocked by environment and deployment configuration:

- `auth`: configure Firebase service account credentials.
- `stripe`: configure secret key, webhook secret, and monthly/yearly price ids.
- `cors`: configure deployed public HTTPS frontend origins.

## Next Cycle

Keep improving launch handoff without weakening guardrails. The next useful
candidate is to add a small deploy-readiness command or report section that
groups the same blockers by owner/surface: Railway backend, Vercel frontend,
Stripe dashboard, Firebase, and GitHub secrets.
