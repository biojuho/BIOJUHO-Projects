# AutoResearch Loop: Browser Stale-Backend Contract

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the live-backend browser smoke suite classify a stale backend before running expensive browser steps, so launch QA points operators at the root cause instead of producing mixed downstream UI failures.

## Scope and Owned Paths

- `scripts/run_browser_smoke_suite.py`
- `backend/tests/test_smoke.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Workspace modernization radar refreshed:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-browser-stale-backend.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_BROWSER_STALE_BACKEND.md`
  - Result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## A/B Hypothesis

Baseline: run the full browser suite against whatever backend is listening on `8002`.

Variant: before launching child browser smokes, fetch `/openapi.json` from the configured backend and require the routes used by the suite:

- `/products/`
- `/products/page`
- `/qr-events/kpis`
- `/qr-events/kpis/trend`
- `/qr-tokens/products/{product_id}`
- `/sensor-devices`
- `/sensor-devices/{sensor_id}`

Primary KPI: lower time-to-actionable-failure for stale backend processes.

Decision rule: adopt if the current stale backend is classified before child browser tests run, dry-run still works without network calls, focused tests pass, and canonical AgriGuard smoke stays green.

## Baseline Evidence

Previous full browser suite against the current live services:

```powershell
python scripts/run_browser_smoke_suite.py --json-out "..\var\agriguard-browser-smoke-suite-post-launch-wrapper.json" --timeout-ms 30000
```

Result: `1/5` browser steps passed. Failures mixed stale backend symptoms and auth-gated paths:

- Nav smoke failed on QR KPI 404 console errors.
- QR/admin/product-detail smokes failed at product seeding with `503 Firebase authentication is not configured`.
- Direct `GET http://127.0.0.1:8002/openapi.json` showed the live backend exposed old routes such as `/qr-events` and `/qr-events/summary`, but not current QR KPI, QR token admin, or sensor admin routes.

## Variant Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-browser-suite-contract"
```

Result: `25 passed in 31.54s`.

Current live backend contract check:

```powershell
python scripts/run_browser_smoke_suite.py --json-out "..\var\agriguard-browser-smoke-suite-stale-backend-contract.json" --timeout-ms 30000
```

Result: expected fail before child browser steps. The report recorded `prechecks_failed=1`, `total=0`, and missing routes:

- `/qr-events/kpis`
- `/qr-events/kpis/trend`
- `/qr-tokens/products/{product_id}`
- `/sensor-devices`
- `/sensor-devices/{sensor_id}`

Dry-run compatibility:

```powershell
python scripts/run_browser_smoke_suite.py --dry-run --json-out "..\var\agriguard-browser-smoke-suite-contract-dry-run.json"
```

Result: dry-run still produced the five-step command plan and did not run the backend OpenAPI check.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-browser-stale-backend-contract.json"
```

Result: `passed=5, failed=0, total=5`.

## Adopt Decision

Adopt the backend OpenAPI precheck in the browser suite. It improves launch QA by distinguishing a stale/rebuilt-required backend from UI regressions and Firebase-auth launch blockers.

## Remaining Launch Blocker

This does not make authenticated browser paths pass. The current live backend still needs to be recreated from current code and launched with operator-provided Firebase Admin credentials, app-scoped launch secrets, public HTTPS verify URL, and allowed origins.
