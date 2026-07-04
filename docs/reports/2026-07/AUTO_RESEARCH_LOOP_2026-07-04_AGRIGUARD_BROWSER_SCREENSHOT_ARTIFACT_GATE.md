# AutoResearch Loop: AgriGuard Browser Screenshot Artifact Gate

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Decision: adopt variant
- Commit target: current branch after verification

## Objective

Harden AgriGuard launch evidence so app-click browser smoke cannot pass while
its screenshot evidence is missing, empty, or corrupt.

## External Sources Checked

- Firebase Admin SDK setup docs: production server auth still depends on a
  Firebase project, service account, and credential configuration file; this
  keeps the existing Firebase service-account blocker classified as external.
  Source: https://firebase.google.com/docs/admin/setup
- Playwright visual comparison docs: Playwright treats screenshots as durable
  test artifacts and calls out environment consistency for reliable screenshot
  evidence. Source: https://playwright.dev/docs/test-snapshots
- GitHub autoresearch comparison: `uditgoenka/autoresearch` frames autonomous
  work as modify, verify, keep/discard loops with bounded commands. Source:
  https://github.com/uditgoenka/autoresearch
- Veritas AutoResearch source: latest observed `main` from
  `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  was `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Contract

- Baseline: aggregate browser smoke trusted child JSON checks and individual
  `screenshot_written` checks. The aggregate report did not verify screenshot
  bytes, PNG headers, dimensions, or admin-route screenshot directory exposure.
- Variant: aggregate browser smoke recursively discovers `screenshot` and
  `screenshotDir` fields from child reports, validates PNG signature,
  dimensions, and minimum byte size, and fails the step when screenshot evidence
  is invalid. Admin-route smoke now exposes `screenshotDir` in its JSON report.
- Primary KPI: aggregate browser report includes screenshot artifact totals and
  fails if any discovered screenshot artifact is invalid.
- Guardrails: existing child checks, backend contract prechecks, proxy
  alignment, route-click coverage, backend tests, frontend build/lint, contracts
  compile/tests.

## Changed Paths

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
- `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/run_browser_smoke_suite.py apps/AgriGuard/scripts/admin_routes_browser_smoke.py apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: `32 passed`.
- `python -m py_compile apps/AgriGuard/scripts/run_browser_smoke_suite.py apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
  - Result: pass.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-screenshot-artifacts.json --output-dir var\agriguard-browser-smoke-suite-screenshot-artifacts --timeout-ms 30000`
  - Result: `status=pass`, `passed=6`, `failed=0`, `checks_passed=135`,
    `checks_failed=0`, `prechecks_passed=2`, `screenshot_artifacts_passed=18`,
    `screenshot_artifacts_failed=0`.
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-screenshot-artifact-gate.json`
  - Result: `passed=5`, `failed=0`, `total=5`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-screenshot-artifact-gate.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`,
    `operator_action_ids=["set_firebase_service_account_file"]`,
    `env_validation_ready_for_preflight=true`, `env_validation_placeholder_count=0`.

## Decision

Adopted. The variant improves launch evidence quality without changing product
runtime behavior and without regressing the canonical AgriGuard smoke scope.

## Remaining Blocker

Guarded launch remains blocked only on the external operator action:
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.` The local code,
browser suite, and AgriGuard workspace smoke are green.

## Next Cycle

Continue launch hardening around consumer-facing verification and operator
handoff surfaces. Do not mark launch complete until a real Firebase Admin
service-account JSON file is supplied outside the repo and strict guarded launch
preflight reaches `ready`.
