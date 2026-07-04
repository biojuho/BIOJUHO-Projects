# AutoResearch Loop: AgriGuard Required Screenshot Artifact Gate

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Decision: adopt variant
- Parent cycle: browser screenshot artifact validation

## Objective

Make the AgriGuard aggregate browser smoke fail closed when an executed child
browser step does not expose at least one valid screenshot artifact, and ensure
child-process timeouts still produce aggregate failure evidence.

## A/B Contract

- Baseline: the aggregate browser suite failed corrupt screenshot artifacts, but
  a child report with no `screenshot` or `screenshotDir` fields could still
  contribute zero screenshot artifacts without failing the step. A first live
  strict-run attempt also showed that a child process timeout could abort the
  aggregate before writing the top-level JSON report.
- Variant: every non-dry-run child step must pass its normal checks, produce at
  least one valid screenshot artifact, and avoid screenshot artifact failures.
  Child subprocess timeouts are caught and serialized as failed step evidence
  with redacted commands, timeout seconds, and any partial stdout/stderr tails.
- Primary KPI: aggregate browser smoke reports
  `screenshot_artifacts_missing_steps=[]` and `screenshot_artifacts_failed=0`
  for a passing run.
- Guardrails: all existing browser step checks, backend contract and proxy
  prechecks, screenshot PNG validation, focused backend tests, and canonical
  AgriGuard workspace smoke.

## Changed Paths

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/run_browser_smoke_suite.py apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: `35 passed`.
- `python -m py_compile apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - Result: pass.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-screenshot-required-v2.json --output-dir var\agriguard-browser-smoke-suite-screenshot-required-v2 --timeout-ms 30000`
  - Result: `status=pass`, `passed=6`, `failed=0`, `checks_passed=135`,
    `checks_failed=0`, `prechecks_passed=2`, `screenshot_artifacts_total=18`,
    `screenshot_artifacts_failed=0`, `screenshot_artifacts_missing_steps=[]`.
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-screenshot-required-v2.json`
  - Result: `passed=5`, `failed=0`, `total=5`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-screenshot-required-v2.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`,
    `operator_action_ids=["set_firebase_service_account_file"]`,
    `env_validation_ready_for_preflight=true`, `env_validation_placeholder_count=0`.

## Decision

Adopted. The variant makes the aggregate browser evidence stricter and more
diagnostic without changing application runtime behavior. The stricter live
suite passed with 18 valid screenshot artifacts and no missing artifact steps.

## Remaining Blocker

Guarded launch remains externally blocked by the missing host-local Firebase
Admin service-account JSON file:
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Next Cycle

Continue product hardening on the next operator-visible launch gap. The launch
completion claim still requires a real Firebase service-account file outside the
repo and a guarded launch status of `ready`.
