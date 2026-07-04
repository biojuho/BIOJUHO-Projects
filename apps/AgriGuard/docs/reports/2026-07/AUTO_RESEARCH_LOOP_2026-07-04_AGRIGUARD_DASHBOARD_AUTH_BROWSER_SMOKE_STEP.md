# AutoResearch Loop - AgriGuard Dashboard Auth Browser Smoke Step

Date: 2026-07-04

## Hypothesis

The dashboard auth recovery screen was previously verified manually and by Vitest, but the aggregate live browser smoke suite only covered authenticated dashboard navigation. A future regression in the tokenless first-screen recovery path could pass the suite. The unauthenticated dashboard recovery path should be a first-class browser smoke step.

## Changes

- Added `apps/AgriGuard/scripts/dashboard_auth_browser_smoke.py`.
  - Opens the dashboard with `agriguard-operator-token` cleared.
  - Verifies the auth heading, inline recovery copy, token textbox, retry button, nonblank body, and no horizontal overflow.
  - Saves the smoke operator token through the UI.
  - Verifies the dashboard loads `Consumer QR KPIs` after retry.
  - Treats the initial 401 console resource error as expected, while still failing on unexpected console/page/request errors.
- Added `dashboard_auth_recovery` as the first step in `run_browser_smoke_suite.py`.
- Updated `test_smoke.py` to assert the new suite step and mobile propagation.

## Verification

- `python apps/AgriGuard/scripts/dashboard_auth_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token browser-smoke-token --mobile --json-out var/agriguard-dashboard-auth-browser-smoke.json --screenshot var/agriguard-dashboard-auth-browser-smoke.png --timeout-ms 30000`
  - 14/14 checks passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - 30 passed.
- Aggregate browser smoke:
  - `var/agriguard-browser-smoke-suite-dashboard-auth-recovery-step.json`
  - 6/6 steps passed; 135/135 checks passed; 2/2 prechecks passed.
- Workspace smoke:
  - `var/workspace-smoke-agriguard-dashboard-auth-recovery-browser-step.json`
  - 5/5 AgriGuard checks passed.
- Guarded launch status:
  - `var/agriguard-guarded-launch-status-dashboard-auth-recovery-browser-step.json`
  - status `blocked`; blocker class `preflight_blocked`;
  - env validation ready for preflight with 0 placeholders;
  - remaining operator action `set_firebase_service_account_file`;
  - remaining preflight error `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Launch Readiness Result

This loop promotes dashboard auth recovery from manual/Vitest evidence into the live browser smoke suite. The local launch-readiness evidence remains green. The only remaining launch blocker is still the external Firebase Admin service-account JSON file.
