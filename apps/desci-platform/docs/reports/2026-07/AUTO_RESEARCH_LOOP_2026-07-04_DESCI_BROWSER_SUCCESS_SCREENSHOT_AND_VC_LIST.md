# AutoResearch Loop: DeSci Browser Success Screenshot and VC List

Date: 2026-07-04

## Objective

Improve dashboard click evidence for launch review by preserving a visual
success artifact, then fix the dashboard VC list instability surfaced by the
canonical workspace smoke.

## A/B Contract

- Baseline A: browser-smoke success runs wrote JSON evidence only. Failed runs
  could keep Playwright traces, but successful dashboard runs had no screenshot
  for UI review.
- Variant A: add optional `--screenshot-dir` to capture PNG screenshots after
  successful checks and record them in browser-smoke JSON.
- Baseline B: after Variant A, `desci` workspace smoke exposed an intermittent
  frontend unit failure in `DashboardLists.test.jsx`; `VCMatchList` could refetch
  when locale function identity changed and then render stale success plus error.
- Variant B: keep Variant A and stabilize `VCMatchList` by depending on the
  localized fallback string, clearing stale matches on failure, and using the
  existing `/vcs` dashboard endpoint contract.
- Decision rule: adopt only if targeted browser smoke writes a real PNG,
  frontend unit tests pass in full, and `desci` workspace smoke returns 8/8.

## Implementation

- Added `screenshot_path` to browser-smoke reports and `screenshot_artifacts` to
  browser-smoke JSON.
- Added `--screenshot-dir` and captured full-page PNGs only after successful
  checks, preserving failure trace behavior.
- Stabilized `VCMatchList` fetch dependencies and stale-data cleanup.
- Added/used dashboard list coverage for the existing `/vcs` endpoint contract.

## Verification

- `python -m py_compile scripts/browser_smoke.py`
  - Result: passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_release_gate.py -q`
  - Result: `147 passed`.
- `npm run test:lts -- DashboardLists`
  - Result: `7 passed`.
- `npm run test:lts -- --fileParallelism false`
  - Result: `43 files passed`, `201 tests passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var/browser-smoke-success-screenshots-2026-07-04-rerun --json-out var/browser-smoke-dashboard-success-screenshot-2026-07-04-rerun.json --trace-on-failure-dir var/browser-smoke-dashboard-success-screenshot-2026-07-04-rerun-traces`
  - Result: OK.
  - Screenshot: `var/browser-smoke-success-screenshots-2026-07-04-rerun/dashboard-readiness-refresh.png`.
  - JSON recorded `screenshot_artifacts[0].check_name=dashboard-readiness-refresh`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-browser-success-screenshot-2026-07-04-fixed.json`
  - Result: `8/8 passed`.

## Decision

Adopted. Successful dashboard browser-smoke runs can now leave visual evidence,
and the dashboard VC list no longer refetches from an unstable locale function
identity during tests or runtime re-renders.
