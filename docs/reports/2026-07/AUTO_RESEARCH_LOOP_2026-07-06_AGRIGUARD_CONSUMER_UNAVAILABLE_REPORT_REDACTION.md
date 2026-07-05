# Auto Research Loop - AgriGuard Consumer Unavailable Report Redaction

Date: 2026-07-06

## Source Basis

- OWASP logging and secrets-management guidance supports excluding bearer-like tokens and sensitive identifiers from durable operational artifacts.
- The consumer unavailable smoke can run against real public verify routes while simulating backend outage behavior. Persisted JSON evidence should prove the outage UX without storing the raw QR token.

## Change

- Added public QR route redaction helpers to `apps/AgriGuard/scripts/consumer_verify_unavailable_browser_smoke.py`.
- The browser workflow still navigates with the requested token internally, but the returned JSON report now redacts:
  - `/verify/{token}` route URLs
  - `/api/qr/{token}/verify` API URLs
  - raw token occurrences in check details and nested response metadata
- Added `test_consumer_verify_unavailable_browser_smoke_redacts_report_token`.

## Verification

- Focused unit checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_consumer_verify_unavailable_browser_smoke_redacts_report_token -q`
  - Result: `1 passed`.
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_consumer_verify_unavailable_browser_smoke_route_and_viewport -q`
  - Result: `1 passed`.
- Existing frontend preview check:
  - `Invoke-WebRequest http://127.0.0.1:5174/`
  - Result: `FRONTEND_5174_STATUS=200`.
- Intercepted browser smoke:
  - Command: `python apps\AgriGuard\scripts\consumer_verify_unavailable_browser_smoke.py --base-url http://127.0.0.1:5174 --token unavailable-secret-token --intercept-api-failure --json-out var\agriguard-consumer-unavailable-redaction-2026-07-06.json --screenshot var\agriguard-consumer-unavailable-redaction-2026-07-06.png --timeout-ms 30000`
  - Result: `15/15 PASS`.
- Redaction probe:
  - Raw token present: `False`.
  - JSON redaction marker count: `5`.
  - Persisted route and API URLs contain `<redacted-public-qr-token>`.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-consumer-unavailable-redaction-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Consumer unavailable browser smoke evidence now avoids storing raw public QR tokens. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
