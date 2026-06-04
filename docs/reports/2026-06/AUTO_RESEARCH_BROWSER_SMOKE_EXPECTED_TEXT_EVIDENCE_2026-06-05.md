# Browser Smoke Expected Text Evidence

- Date: 2026-06-05
- Scope: manifest-backed dev-server browser smoke
- Baseline: browser smoke reports showed route pass/fail but did not record which expected text assertions matched.
- Variant: add per-route `expected_text_count`, `matched_expected_text`, and `missing_expected_text` fields, and show `expected=x/y` in Markdown results.
- Primary KPI: stronger direct browser QA evidence for launch-critical app surfaces.
- Guardrails: preserve existing route pass/fail behavior; keep manifest validation unchanged; do not weaken browser assertions; live dashboard smoke remains green.

## Adopted Variant

Adopted. The dashboard browser-smoke report now records `expected=11/11` in Markdown and stores the matched expected text list in JSON, including `Queue #2` and `GitHub source-refresh token boundary`.

## Changed Paths

- `ops/scripts/dev_server_browser_smoke.py`
- `tests/test_dev_server_browser_smoke.py`

## Verification

- `python -m py_compile ops\scripts\dev_server_browser_smoke.py tests\test_dev_server_browser_smoke.py` -> pass
- `python -m pytest tests\test_dev_server_browser_smoke.py -q` -> `6 passed`
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-expected-text-evidence-2026-06-05.json` -> `2/2 ready`
- `python ops\scripts\dev_server_browser_smoke.py --validate-only --target dashboard-frontend --json-out var\dev-server-browser-smoke-expected-text-validate-2026-06-05.json --markdown-out var\dev-server-browser-smoke-expected-text-validate-2026-06-05.md` -> valid
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_EXPECTED_TEXT_2026-06-05.md` -> `1/1 routes`, `failed=0`, `expected=11/11`
- Managed dashboard cleanup: final status `0/2 ready`

## Remaining Boundary

This strengthens browser QA evidence. It does not complete credential-gated external work; Canva and GitHub live operations still require operator credentials.

global_objective_complete=false
