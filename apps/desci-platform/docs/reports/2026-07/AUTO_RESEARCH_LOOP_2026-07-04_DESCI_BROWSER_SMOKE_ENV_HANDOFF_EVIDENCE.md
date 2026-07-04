# AutoResearch Loop: DeSci Browser-Smoke Env Handoff Evidence

Date: 2026-07-04

## Objective

Make the dashboard env handoff browser-click proof durable in JSON evidence, not
only in the pass/fail result of `dashboard-readiness-refresh`.

## A/B Contract

- Baseline: browser smoke clicked the dashboard handoff button and validated
  clipboard contents, but the JSON report only retained generic
  `next_action_required_env`.
- Variant: add `launch_control.launch_env_handoff` with required env, optional
  env, placeholder copy lines, line count, source, and bad-line audit.
- Primary KPI: the browser-smoke JSON is enough to audit the exact dashboard
  handoff without replaying Playwright traces.
- Guardrails: targeted browser smoke remains green and no raw secret-shaped
  values, URLs, or remediation prose appear in the handoff copy lines.

## Implementation

- Added browser-smoke helpers for launch env handoff grouping and placeholder
  copy-line auditing.
- Nested the new evidence under `launch_control.launch_env_handoff` to avoid
  colliding with the product-smoke top-level `launch_env_handoff` contract.
- Extended `backend/tests/test_browser_smoke.py` to pin the JSON evidence shape.

## Verification

- `python -m py_compile scripts/browser_smoke.py`
  - Result: passed.
- `python -m pytest backend/tests/test_browser_smoke.py -q`
  - Result: `43 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --json-out var/browser-smoke-dashboard-env-handoff-evidence-2026-07-04.json --trace-on-failure-dir var/browser-smoke-dashboard-env-handoff-evidence-2026-07-04-traces`
  - Result: OK.
  - JSON evidence:
    - `status=blocked`
    - required env: `GOOGLE_APPLICATION_CREDENTIALS`,
      `FIREBASE_SERVICE_ACCOUNT_JSON`, `STRIPE_SECRET_KEY`,
      `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`,
      `STRIPE_PRICE_PRO_YEARLY`, `ALLOWED_ORIGINS`
    - optional env: `RABBITMQ_URL`, `PINATA_JWT`, `PINATA_API_KEY`,
      `PINATA_API_SECRET`, `GROBID_ENABLED`, `GROBID_URL`
    - `operator_copy_line_count=19`
    - `bad_copy_lines=[]`

## Decision

Adopted. Browser-smoke artifacts now preserve the actual dashboard env handoff
contract, so a green click run leaves machine-readable evidence for later
release-gate or audit review.
