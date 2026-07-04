# AutoResearch Loop: DeSci Dashboard Env Handoff

Date: 2026-07-04

## Objective

Close the operator UX gap after the product-smoke and release-gate env handoff
work. The launch artifacts now expose placeholder-only env keys, but dashboard
operators still had to copy scattered per-action remediation cards.

## A/B Contract

- Baseline: dashboard readiness showed `/launch` next actions and per-action
  copy buttons. Env keys were visible, but not grouped into one secret-manager
  handoff.
- Variant: add a dashboard `Launch env handoff` block that deduplicates
  required and optional env keys and copies only `<set-secure-value>`
  placeholders.
- Primary KPI: a browser-clicked dashboard copy path produces one
  placeholder-only env handoff for all launch blockers and warnings.
- Guardrails: per-action copy remains available, `/ready` and `/launch` drift
  detection remains intact, and no secret-shaped values or remediation prose
  appear in the env handoff clipboard payload.

## Implementation

- Added required/optional env handoff derivation in
  `frontend/src/components/ProductReadinessPanel.jsx`.
- Added a dashboard handoff block and `Copy launch env handoff` button inside
  the existing launch action queue.
- Extended `ProductReadinessPanel` unit coverage for required/optional grouping
  and placeholder-only clipboard content.
- Extended the dashboard readiness browser smoke to click the handoff button and
  verify the clipboard payload.

## Verification

- `npm run test:lts -- ProductReadinessPanel`
  - Result: `9 passed`.
- `python -m pytest backend/tests/test_browser_smoke.py -q`
  - Result: `43 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --json-out var/browser-smoke-dashboard-env-handoff-2026-07-04.json --trace-on-failure-dir var/browser-smoke-dashboard-env-handoff-2026-07-04-traces`
  - Result: dashboard readiness refresh OK.
  - Browser clicked the env handoff button and verified placeholder lines for
    `GOOGLE_APPLICATION_CREDENTIALS`, `STRIPE_SECRET_KEY`,
    `STRIPE_PRICE_PRO_MONTHLY`, `ALLOWED_ORIGINS`, `PINATA_JWT`, and
    `GROBID_URL`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-dashboard-env-handoff-2026-07-04.json`
  - Result: `8/8 passed`.

## Decision

Adopted. Dashboard operators now get the same secret-safe env handoff in the UI
that product-smoke and release-gate artifacts expose. Production release still
remains fail-closed until real auth, Stripe, CORS, and optional launch-hardening
values are installed in the target runtime.
