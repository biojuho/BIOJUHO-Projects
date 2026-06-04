# Browser Smoke Markdown Expected Text Evidence

- Date: 2026-06-05
- Scope: manifest-backed dev-server browser smoke Markdown reporting
- Baseline: Markdown reports showed route pass/fail and `expected=x/y`, but the matched expected strings were only visible in JSON.
- Variant: add a Markdown `Expected Text Evidence` section that lists matched and missing expected text per route.
- Primary KPI: human-auditable direct browser QA evidence without opening the JSON artifact.
- Guardrails: preserve existing route execution, manifest validation, JSON schema fields, and route pass/fail behavior.

## Adopted Variant

Adopted. The live dashboard browser-smoke Markdown report now lists all 11 matched expected strings and `missing: none`, including `Queue #2` and `GitHub source-refresh token boundary`.

## Changed Paths

- `ops/scripts/dev_server_browser_smoke.py`
- `tests/test_dev_server_browser_smoke.py`

## Evidence Artifacts

- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_MARKDOWN_2026-06-05.md`
- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_MARKDOWN_2026-06-05.json`

## Verification

- `python -m py_compile ops\scripts\dev_server_browser_smoke.py tests\test_dev_server_browser_smoke.py` -> pass
- `python -m pytest tests\test_dev_server_browser_smoke.py -q` -> `7 passed`
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-markdown-expected-text-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_MARKDOWN_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_MARKDOWN_2026-06-05.md` -> `pass: 1/1 routes, failed=0`

## Remaining Boundary

This improves browser QA evidence auditability. It does not complete credential-gated external live operations; Canva OAuth/OpenAPI execution and GitHub source-refresh credentials remain operator-bound.

global_objective_complete=false
