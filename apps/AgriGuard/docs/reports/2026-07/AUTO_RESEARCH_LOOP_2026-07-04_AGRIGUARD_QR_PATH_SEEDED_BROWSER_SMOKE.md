# AutoResearch Loop - AgriGuard QR Path Seeded Browser Smoke

Date: 2026-07-04
App: AgriGuard
Cycle: Public QR path browser-smoke reliability

## Baseline

`qr_path_browser_smoke.py` used `mock-0` as its default manual verification token. In a fresh launch-style database, that token is not an issued public QR token, so the app correctly renders the unverified QR state.

Proxy-mode baseline evidence:

- Command: `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5199 --json-out var/agriguard-qr-path-api-proxy-2026-07-04/qr-path-api-proxy-mobile.json --screenshot-dir var/agriguard-qr-path-api-proxy-2026-07-04/qr-path-api-proxy-mobile-screens --timeout-ms 30000`
- Result: 20/21 checks passed
- Failed: `manual_verify_batch_evidence_visible`
- Cause: `manualToken` was `mock-0`, and the fresh DB returned the safe unverified public QR state.

## Variant

Adopted backend seeding for the QR path smoke:

- Added `--api-url` and `--operator-token`.
- When `--api-url` is provided and `--manual-token` is omitted, the smoke creates a product through the backend.
- The smoke extracts the issued public verify token from `qr_code`.
- The scan/manual verify/invalid verify browser path then runs against a real issued token.
- Existing `--manual-token` behavior is preserved for explicit fixtures.

## Evidence

- `python -m py_compile apps/AgriGuard/scripts/qr_path_browser_smoke.py`
  - Status: pass
- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-qr-path-smoke-seed"`
  - Result: 11 passed
- Seeded proxy-mode browser smoke:
  - Command: `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5199 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var/agriguard-qr-path-api-proxy-2026-07-04/qr-path-api-proxy-seeded-mobile.json --screenshot-dir var/agriguard-qr-path-api-proxy-2026-07-04/qr-path-api-proxy-seeded-mobile-screens --timeout-ms 30000`
  - Result: 22/22 checks passed
  - Seeded product id: `7bb98d4d-ef70-4676-a048-83cc16b82158`
  - Backend audit log observed `POST /products/` and `GET /api/qr/{issued-token}/verify`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-qr-path-seeded-browser.json`
  - Status: complete
  - Passed: 5/5
  - Failed: 0
  - Covered: frontend lint, frontend build, contracts compile, contracts tests, backend tests

## Decision

Adopt the seeded QR path browser smoke. It validates the launch-critical public QR journey against a fresh database without relying on pre-existing magic fixtures.
