# AutoResearch Loop - AgriGuard Browser Suite Proxy Alignment Precheck

Date: 2026-07-04
App: AgriGuard
Cycle: Browser smoke backend/proxy alignment

## Baseline

The aggregate browser smoke suite accepted any `--api-url` whose OpenAPI contract contained the required launch routes. A run with `--api-url http://127.0.0.1:8102` passed that contract check, but the frontend at `http://127.0.0.1:5174` used its `/api` proxy target instead.

Impact:

- QR path, admin routes, and product-detail child smokes seeded data into one backend and clicked a frontend wired to another backend.
- The resulting failures looked like UI regressions even though the configured launch backend at `http://127.0.0.1:8002` passed the same app-click suite.

## Variant

Added a `backend_proxy_alignment` precheck to `run_browser_smoke_suite.py`.

The suite now:

- keeps the existing OpenAPI contract check for required launch routes,
- seeds a precheck product through `--api-url`,
- reads the same product back through `BASE_URL/api`,
- stops before browser execution if the seeded product is not visible through the frontend proxy.

The existing `--skip-backend-contract-check` option now skips both live backend/proxy prechecks for intentional unavailable-backend probes.

## Evidence

- `python -m py_compile apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: 30 passed
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8102 --output-dir var\agriguard-browser-smoke-suite-proxy-mismatch-20260704 --json-out var\agriguard-browser-smoke-suite-proxy-mismatch-20260704.json --timeout-ms 30000 --mobile`
  - Result: expected failure before browser execution
  - Summary: `prechecks_total=2`, `prechecks_passed=1`, `failed_precheck_names=["backend_proxy_alignment"]`, `total=0`
  - Detail: seeded product was not visible through frontend `/api`; `--api-url` may target a different backend than the frontend proxy
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --output-dir var\agriguard-browser-smoke-suite-proxy-alignment-20260704 --json-out var\agriguard-browser-smoke-suite-proxy-alignment-20260704.json --timeout-ms 30000 --mobile`
  - Result: pass
  - Summary: `prechecks_total=2`, `prechecks_passed=2`, `total=5`, `checks_passed=121`, `checks_failed=0`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-suite-proxy-alignment-20260704.json`
  - Result: pass
  - Summary: `passed=5`, `failed=0`, `total=5`

## Decision

Adopt the proxy-alignment precheck. It turns backend/proxy drift into an explicit harness failure while preserving the green app-click path for the current launch backend.
