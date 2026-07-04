# AutoResearch Loop - AgriGuard Firebase Compose Classification

Date: 2026-07-05

## Objective

Keep AgriGuard launch-blocker handoffs precise when Docker Compose fails during
interpolation because `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` is missing. The
operator should receive the Firebase credential action, not a misleading Docker
readiness action when Docker itself is healthy.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
- `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_FIREBASE_COMPOSE_CLASSIFICATION.md`

## External Sources Checked

- Docker Compose variable interpolation documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/`
- Docker Compose environment-variable precedence documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/`
- Docker Compose secrets documentation:
  `https://docs.docker.com/compose/how-tos/use-secrets/`
- Veritas AutoResearch source:
  `https://github.com/Veritas-7/autoresearch-skill-system`
  - Latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

Baseline: when Compose interpolation failed because the required Firebase env
var was missing, the preflight emitted a generic Compose config failure. The
operator packet mapped that generic message to `fix_docker_readiness`, even
though Docker daemon readiness passed.

Variant: classify Compose stderr that names
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and `missing a value` as a Firebase
credential blocker. Keep generic Compose config failures generic.

Primary KPI: the real blocked launch handoff lists only
`set_firebase_service_account_file` for the missing-Firebase path while Docker
daemon remains `ok=true`.

Decision rule: adopt only if focused tests, real blocked handoff evidence,
canonical AgriGuard smoke, and browser click smoke all pass.

## Adopted Variant

Adopted. `check_docker_readiness()` now recognizes the known Compose
interpolation message for the required Firebase secret path and emits a
Firebase-specific error. The existing generic Compose config error remains for
non-interpolation failures.

During browser verification, the admin routes smoke uncovered a separate
evidence flake caused by accumulated sensor fixtures: the new sensor could land
on page 2 of `/sensor-devices`. The smoke now assigns a unique zone and applies
the UI `Zone filter` before asserting the newly registered sensor is visible.

## Verification

- `python -m ruff check apps/AgriGuard/scripts/admin_routes_browser_smoke.py apps/AgriGuard/scripts/launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/scripts/admin_routes_browser_smoke.py apps/AgriGuard/scripts/launch_env_preflight.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q`
  - Result: `66 passed`
- Real missing-Firebase launch handoff:
  - Command used `launch_compose.py --env-file var\agriguard-launch-operator-missing-firebase-compose-classification.env ... --service backend`
  - Result: expected exit code `1`
  - Docker daemon: `ok=true`, version `29.2.1`
  - Compose config: failed with required Firebase env interpolation
  - Operator packet action IDs: `set_firebase_service_account_file`
  - Readiness summary: `status=blocked`, `blocker_class=preflight_blocked`
- Initial aggregate browser suite:
  - Result: failed in `admin_routes:unhandled_exception`
  - Root cause: accumulated smoke sensors exceeded first-page registry capacity
  - Fix: unique zone plus UI filter in `admin_routes_browser_smoke.py`
- `python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-admin-routes-browser-smoke-zone-filter.json --screenshot-dir var\agriguard-admin-routes-browser-smoke-zone-filter-screens --timeout-ms 120000`
  - Result: pass
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-missing-firebase-compose-classification-retry.json --output-dir var\agriguard-browser-smoke-suite-missing-firebase-compose-classification-retry --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshots_passed=18`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-missing-firebase-compose-classification-retry.json`
  - Result: `passed=5, failed=0`

## Commit And Push Status

This report is part of the implementation commit for the cycle:
`Classify missing AgriGuard Firebase compose env precisely`.

Push target: `origin feat/shared-llm-modernization-2026-06-19`.

## Remaining Blocker

AgriGuard launch still requires a real outside-repo Firebase Admin service
account JSON. Local evidence now classifies that blocker precisely and keeps
Docker readiness separate from credential readiness.

## Next Cycle

With a real Firebase credential path, rerun guarded launch from the operator env
file and require preflight, compose startup, readiness artifacts, and browser
smoke to pass together before clearing the launch gate.
