# AgriGuard Consumer Verify Unavailable Intercept

Date: 2026-07-05

## Loop

- External source refresh: `Veritas-7/autoresearch-skill-system` main/HEAD observed at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Baseline: the consumer verify unavailable browser smoke validated the recovery UI only when the frontend was up and the backend/proxy target was intentionally unavailable.
- Variant shipped: `consumer_verify_unavailable_browser_smoke.py` can now simulate the public verify API outage in Playwright with `--intercept-api-failure`, blocks service workers for deterministic route interception, and records intercepted 503 requests.
- Adoption rule: adopt only if the standalone unavailable smoke, full mobile aggregate suite with `--include-unavailable-check`, AgriGuard scope, and workspace scope are green.

## Browser Evidence

Standalone unavailable smoke:

```powershell
python apps\AgriGuard\scripts\consumer_verify_unavailable_browser_smoke.py --base-url http://127.0.0.1:5174 --intercept-api-failure --json-out var\agriguard-consumer-verify-unavailable-intercept.json --screenshot var\agriguard-consumer-verify-unavailable-intercept.png --timeout-ms 30000
```

Result: 15/15 checks passed.

- `interceptApiFailure`: `true`
- `interceptedApiFailures`: 2
- `serviceWorkers`: `block`

Full mobile browser suite with unavailable check:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --include-unavailable-check --json-out var\agriguard-browser-smoke-suite-unavailable-intercept.json --output-dir var\agriguard-browser-smoke-suite-unavailable-intercept --timeout-ms 30000
```

Result:

- Steps: 7/7
- Prechecks: 2/2
- Checks: 166/166
- Screenshots: 19/19
- `screenshot_artifact_dimension_failures`: `[]`

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`: 46 passed.
- `python scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-unavailable-intercept.json`: complete, 5/5 passed.
- `python scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-unavailable-intercept.json`: complete, 9/9 passed.

## Decision

Adopted. The aggregate browser suite can now exercise the consumer "Verification unavailable" recovery path while the normal backend remains online.

Remaining launch blocker: production launch still requires operator-provided Firebase Admin/service-account configuration outside this local repo change.
