# All Frontends Browser Smoke Expected Text

- Date: 2026-06-05
- Scope: dashboard, AgriGuard, DeSci, and Canva widget preview browser smoke
- Baseline: each frontend had separate browser-smoke evidence, but the new Markdown expected-text evidence had only been proven on the dashboard route.
- Variant: run the manifest-backed browser smoke across all frontend checks and preserve JSON plus Markdown evidence with matched expected text for every route.
- Primary KPI: launch-critical browser QA coverage across all manifest-backed product surfaces.
- Guardrails: all dev-server targets must be ready; every route must pass; every route must report `missing: none`.

## Adopted Variant

Adopted. The integrated browser smoke passed `10/10` routes across `4` frontend targets with `0` failures and `missing: none` for all expected text checks.

## Evidence Artifacts

- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_ALL_FRONTENDS_EXPECTED_TEXT_MARKDOWN_2026-06-05.md`
- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_ALL_FRONTENDS_EXPECTED_TEXT_MARKDOWN_2026-06-05.json`

## Surfaces Covered

- `dashboard-frontend`: `home`, `11/11` expected text matched.
- `agriguard-frontend`: `home`, `registry`, `supply-chain`, all expected text matched.
- `desci-frontend`: `home`, `pricing`, `explore`, `login`, `dashboard-redirect`, all expected text matched.
- `canva-widget-preview`: `preview`, expected text matched.

## Verification

- `python ops\scripts\dev_server_status.py --json-out var\dev-server-status-all-frontends-expected-text-markdown-2026-06-05.json` -> `7/7 ready`
- `python ops\scripts\dev_server_browser_smoke.py --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_ALL_FRONTENDS_EXPECTED_TEXT_MARKDOWN_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_ALL_FRONTENDS_EXPECTED_TEXT_MARKDOWN_2026-06-05.md` -> `pass: 10/10 routes, failed=0`

## Remaining Boundary

This confirms local browser route readiness across manifest-backed surfaces. It does not complete external live operations that require operator credentials, including Canva OAuth/OpenAPI execution and GitHub source-refresh credentials.

global_objective_complete=false
