# AutoResearch Loop - AgriGuard Browser Smoke Defaults

Date: 2026-07-04
App: AgriGuard
Cycle: Browser-smoke launch reliability

## Baseline

Fresh current-state browser validation exposed two verifier defaults that could report a false product failure when the app was running correctly:

- Mobile click-nav smoke without an explicit operator token returned `39/42 PASS`. The dashboard route timed out waiting for `Consumer QR KPIs`, and Chromium logged repeated 401 responses from protected operator endpoints.
- QR path smoke without an API URL returned `20/21 PASS`. It fell back to the stale `mock-0` fixture token, which is invalid in a fresh launch-style database, so the consumer page correctly rendered the unverified QR state instead of batch evidence.

## Variant

Adopted stricter local-smoke defaults:

- `nav_browser_smoke.py` now defaults `--operator-token` to `AGRIGUARD_BROWSER_OPERATOR_TOKEN` or the non-secret local dev-fallback token `browser-smoke-token`.
- `qr_path_browser_smoke.py` no longer silently uses `mock-0` when `--manual-token` is omitted. It seeds a real product token through `AGRIGUARD_BROWSER_API_URL`, an explicit `--api-url`, or the frontend proxy at `BASE_URL/api`.
- Explicit fixture runs can still pass `--manual-token mock-0`.
- Unexpected QR smoke API/browser errors now write a structured failure JSON instead of exiting before evidence is captured.

## Evidence

- `python -m py_compile scripts/nav_browser_smoke.py scripts/qr_path_browser_smoke.py backend/tests/test_smoke.py`
  - Status: pass
- `python -m pytest backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-browser-defaults-final"`
  - Result: `14 passed`
- Mobile click-nav smoke with no explicit token flag:
  - Command: `python scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5174 --mobile --click-nav --json-out ..\var\agriguard-browser-current-nav-fixed-defaults.json --screenshot-dir ..\var\agriguard-browser-current-nav-fixed-defaults-screens --timeout-ms 30000`
  - Result: `47/47 PASS`
- QR path smoke with no explicit API URL or manual token:
  - Command: `python scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --json-out ..\var\agriguard-browser-current-qr-fixed-defaults.json --screenshot-dir ..\var\agriguard-browser-current-qr-fixed-defaults-screens --timeout-ms 30000`
  - Result: `22/22 PASS`
- Full AgriGuard smoke:
  - Command: `python ..\ops\scripts\run_workspace_smoke.py --scope agriguard --json-out ..\var\workspace-smoke-agriguard-browser-defaults.json`
  - Result: `passed=5, failed=0, total=5`

## Decision

Adopt the browser-smoke default hardening. The launch browser checks now exercise authenticated operator navigation and public QR verification against issued data by default, while preserving explicit fixture mode for targeted diagnostics.
