# AutoResearch Loop: AgriGuard Post-DeSci Evidence Refresh

Date: 2026-07-04
App: AgriGuard
Cycle: current local launch evidence refresh after DeSci verification

## Objective

Refresh local AgriGuard launch evidence after the latest compose Firebase env-file bridge work and DeSci evidence refresh.

## Evidence

- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-current-20260704-post-desci.json`
  - Result: `passed=5`, `failed=0`, `total=5`.
  - Covered frontend lint, frontend build, contracts compile, contracts tests, and backend tests.

- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-current-20260704-post-desci.json --output-dir var\agriguard-browser-smoke-suite-current-20260704-post-desci --timeout-ms 120000`
  - Result: `passed=6`, `failed=0`, `total=6`.
  - Browser checks: `checks_passed=135`, `checks_failed=0`, `checks_total=135`.
  - Prechecks: `prechecks_passed=2`, `prechecks_failed=0`.
  - Screenshot artifacts: `screenshot_artifacts_passed=18`, `screenshot_artifacts_failed=0`, `screenshot_artifacts_total=18`.

## Decision

Adopt this as the current AgriGuard local launch evidence snapshot. Local build/test/browser paths remain green. Public guarded launch remains externally blocked until an operator supplies a real Firebase service-account JSON file outside the repository and sets `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` to that path.
