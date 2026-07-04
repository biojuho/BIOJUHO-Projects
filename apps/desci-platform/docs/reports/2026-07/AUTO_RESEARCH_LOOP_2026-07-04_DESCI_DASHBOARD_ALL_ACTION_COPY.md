# AutoResearch Loop: Dashboard All Action Copy

Date: 2026-07-04

## Goal

Exercise the complete launch action clipboard workflow in the browser. The prior dashboard browser smoke verified button presence, the Stripe copy path, copy-all, and env handoff, but did not click every individual launch action copy button.

## A/B Test

- Baseline: only one individual launch action copy path is clicked.
- Variant: `dashboard-readiness-refresh` clicks and validates all six individual launch action copy buttons: Authentication, Stripe billing, CORS origins, RabbitMQ, IPFS, and GROBID.
- KPI: each copied clipboard payload contains the expected launch action title, priority, remediation/env fragments, and no secret-shaped values.

## Result

Variant wins. The browser smoke now exercises each individual launch action copy path and still passes the dashboard readiness check. Feedback validation accepts localized labels while the clipboard payload remains action-specific.

## Evidence

- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q`
  - Result: `46 passed`
- Direct browser smoke:
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var\browser-smoke-dashboard-copy-all-actions-2026-07-04-rerun --json-out var\browser-smoke-dashboard-copy-all-actions-2026-07-04-rerun.json --trace-on-failure-dir var\browser-smoke-dashboard-copy-all-actions-2026-07-04-rerun-traces`
  - Result: `dashboard-readiness-refresh OK`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-copy-all-actions-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-copy-all-actions-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-copy-all-actions-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/browser-smoke-dashboard-copy-all-actions-2026-07-04-rerun.json`
- `apps/desci-platform/var/release-gate-dashboard-copy-all-actions-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-copy-all-actions-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-copy-all-actions-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
