# AutoResearch Loop: AgriGuard Browser Frontend Token Precheck

Date: 2026-07-06

## Objective

Harden AgriGuard launch browser evidence after direct app-click testing found that a frontend built with `VITE_AGRIGUARD_OPERATOR_TOKEN` bypasses the dashboard auth-recovery state and invalidates protected-route smoke checks.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_2026-07-06.md`
  - Result: `github modernization radar valid: 8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis and Decision Rule

- Baseline A: run the aggregate browser suite against the already-running `5174`/`8002` pair.
- Baseline B: run fresh current-checkout frontend/backend with `VITE_AGRIGUARD_OPERATOR_TOKEN` set.
- Variant C: run fresh current-checkout frontend/backend without `VITE_AGRIGUARD_OPERATOR_TOKEN`, using only `AGRIGUARD_BROWSER_OPERATOR_TOKEN` for the smoke runner.
- Decision rule: adopt only if Variant C preserves desktop/mobile browser smoke success, adds a deterministic fail-fast guard for the misconfiguration, does not serialize token values, and canonical AgriGuard smoke remains green.

## Baseline Evidence

- Already-running `5174`/`8002` desktop aggregate smoke:
  - Artifact: `var/agriguard-browser-smoke-suite-2026-07-06-cycle-desktop.json`
  - Result: `failed=1`, failed check `qr_path:public_verify_api_responses_no_store`
  - Finding: direct current-code unit coverage proved the checked-in route sets cache headers, so this was stale running-service evidence rather than a repo regression.
- Fresh current-checkout run with `VITE_AGRIGUARD_OPERATOR_TOKEN` set:
  - Artifacts: `var/agriguard-browser-smoke-suite-2026-07-06-fresh-current-desktop.json`, `var/agriguard-browser-smoke-suite-2026-07-06-fresh-current-mobile.json`
  - Result: both failed `dashboard_auth_recovery` and `admin_routes`
  - Finding: the frontend env token hid the no-token recovery state that those launch smokes intentionally verify.

## Adopted Variant

- Added `frontend_operator_token_env` as a non-dry-run aggregate browser-smoke precheck.
- The precheck fails before child browser steps when `VITE_AGRIGUARD_OPERATOR_TOKEN` is present.
- The precheck report records only that the env var is configured; it never writes the token value.
- Operators should use `AGRIGUARD_BROWSER_OPERATOR_TOKEN` for the smoke runner instead of embedding a bearer token into the frontend.

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_browser_smoke_suite_rejects_frontend_operator_token_env apps/AgriGuard/backend/tests/test_smoke.py::test_browser_smoke_suite_builds_live_backend_steps_and_redacts_operator_token apps/AgriGuard/backend/tests/test_smoke.py::test_browser_smoke_suite_unavailable_check_is_explicit_opt_in -q`
  - Result: `3 passed`
- `VITE_AGRIGUARD_OPERATOR_TOKEN=secret-frontend-token python apps/AgriGuard/scripts/run_browser_smoke_suite.py --skip-backend-contract-check --json-out var/agriguard-browser-smoke-suite-frontend-token-precheck.json --output-dir var/agriguard-browser-smoke-suite-frontend-token-precheck`
  - Result: exit `1`, failed precheck `frontend_operator_token_env`, token value absent from JSON
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: `56 passed`
- Fresh desktop aggregate browser suite without frontend token:
  - Artifact: `var/agriguard-browser-smoke-suite-2026-07-06-token-precheck-desktop.json`
  - Result: `passed=7`, `checks_passed=167`, `prechecks_passed=3`, `screenshot_artifacts_passed=19`
- Fresh mobile aggregate browser suite without frontend token:
  - Artifact: `var/agriguard-browser-smoke-suite-2026-07-06-token-precheck-mobile.json`
  - Result: `passed=7`, `checks_passed=181`, `prechecks_passed=3`, `screenshot_artifacts_passed=19`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-browser-token-precheck.json`
  - Result: `passed=5, failed=0, total=5`

## Decision

Adopt Variant C. The launch browser suite now fails closed on a local frontend-token misconfiguration that would otherwise hide auth-recovery regressions and risk exposing operator bearer credentials.

## Remaining External Blocker

Real compose/browser launch remains blocked until the operator provides a real Firebase Admin service-account `.json` at an absolute host path outside the repo for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue app-click launch hardening against fresh current-checkout servers. Keep using `AGRIGUARD_BROWSER_OPERATOR_TOKEN` for browser-smoke authentication and leave frontend token embedding unset.
