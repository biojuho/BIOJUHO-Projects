# AutoResearch Loop: Dashboard Layout Guard

Date: 2026-07-04

## Goal

Make the screenshot-backed dashboard smoke prove more than successful rendering. The previous check validated readiness copy, launch actions, clipboard flows, and screenshot capture, but it did not fail if the dashboard developed horizontal overflow or clipped launch handoff/action panels.

## A/B Test

- Baseline: `dashboard-readiness-refresh` accepts the dashboard when required text and clipboard flows pass.
- Variant: the same check also probes layout metrics for the readiness panel, launch control, launch env handoff, and each launch action card.
- KPI: the real dashboard browser check passes with no horizontal document overflow, no missing or zero-sized layout targets, and no horizontally clipped launch content.

## Result

Variant wins. The dashboard check now fails on:

- horizontal document overflow
- missing launch layout targets
- zero-sized launch layout targets
- horizontally clipped launch handoff or action panels

The current local dashboard passes the new guard and still emits a valid screenshot artifact through release gate.

## Evidence

- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q`
  - Result: `45 passed`
- Direct browser smoke:
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var\browser-smoke-dashboard-layout-guard-2026-07-04 --json-out var\browser-smoke-dashboard-layout-guard-2026-07-04.json --trace-on-failure-dir var\browser-smoke-dashboard-layout-guard-2026-07-04-traces`
  - Result: `dashboard-readiness-refresh OK`
- Runtime release gate:
  - `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-layout-guard-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-layout-guard-2026-07-04.json`
  - Result: `Release gate OK`
- Full workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-layout-guard-2026-07-04.json`
  - Result: `8/8 passed`

## Local Artifacts

- `apps/desci-platform/var/browser-smoke-dashboard-layout-guard-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-layout-guard-2026-07-04.json`
- `apps/desci-platform/var/release-gate-dashboard-layout-guard-screenshots-2026-07-04/dashboard-readiness-refresh.png`
- `apps/desci-platform/var/workspace-smoke-desci-dashboard-layout-guard-2026-07-04.json`

The PNG remains a local runtime artifact and is not committed.
