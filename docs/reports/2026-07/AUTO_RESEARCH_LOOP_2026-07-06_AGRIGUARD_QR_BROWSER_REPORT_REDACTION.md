# Auto Research Loop - AgriGuard QR Browser Report Redaction

Date: 2026-07-06

## Source Basis

- OWASP logging and secrets-management guidance support excluding credentials, bearer-like tokens, and sensitive connection material from operational artifacts.
- AgriGuard public QR tokens are intentionally user-facing, but the browser smoke can be pointed at non-disposable environments. Persisted smoke JSON should therefore avoid storing raw valid QR tokens.

## Change

- Added public QR token redaction helpers to `apps/AgriGuard/scripts/qr_path_browser_smoke.py`.
- The browser workflow still uses the real token internally, but the returned JSON report now redacts:
  - top-level `manualToken`
  - seeded token metadata
  - `/verify/{token}` URLs
  - `/api/qr/{token}/verify` URLs
  - `agri://verify/{token}` values
- Added `test_qr_path_browser_smoke_redacts_public_tokens_from_report`.

## Verification

- Focused unit checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_qr_path_browser_smoke_redacts_public_tokens_from_report -q`
  - Result: `1 passed`.
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_qr_path_browser_smoke_tracks_public_verify_cache_headers -q`
  - Result: `1 passed`.
- Fresh isolated browser smoke:
  - Backend: `http://127.0.0.1:8003`
  - Frontend: `http://127.0.0.1:5198`
  - Command: `python apps\AgriGuard\scripts\qr_path_browser_smoke.py --base-url http://127.0.0.1:5198 --api-url http://127.0.0.1:8003 --operator-token browser-smoke-token --json-out var\agriguard-qr-path-redaction-browser-2026-07-06.json --screenshot-dir var\agriguard-qr-path-redaction-browser-2026-07-06 --timeout-ms 30000`
  - Result: `27/27 PASS`.
- Redaction probe:
  - `manualToken=<redacted-public-qr-token>`
  - `seededManualToken.token=<redacted-public-qr-token>`
  - public verify API URLs contained `<redacted-public-qr-token>` and kept `Cache-Control: no-store`.
  - JSON redaction marker count: `14`.
- Temporary helper services on ports `8003` and `5198` were stopped after the run.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-qr-browser-report-redaction-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

QR browser smoke evidence now avoids storing raw public QR tokens. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
