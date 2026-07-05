# Auto Research Loop - AgriGuard Admin Routes Report Redaction

Date: 2026-07-06

## Source Basis

- OWASP logging and secrets-management guidance supports excluding bearer-like tokens and sensitive operational identifiers from durable logs and smoke-test artifacts.
- The admin routes smoke reissues QR labels and captures UI body-text samples. Those samples can include both public verify routes and displayed token prefixes, so the JSON report should retain behavioral evidence without retaining raw QR token material.

## Change

- Added public QR report redaction helpers to `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`.
- The browser workflow still uses the real operator token and exercises QR reissue normally, but persisted JSON now redacts:
  - `agri://verify/{token}` values
  - `/verify/{token}` and `/api/qr/{token}/verify` route shapes
  - QR token table values rendered as `Token...State` in body-text samples
- Added `test_admin_routes_browser_smoke_redacts_public_qr_tokens_from_report`.

## Verification

- Focused unit checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_redacts_public_qr_tokens_from_report -q`
  - Result: `1 passed`.
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_uses_operator_token_env apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_uses_phone_viewport_for_mobile_default apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_uses_viewport_screenshots_for_fixed_nav apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_attaches_page_diagnostics apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_classifies_expected_missing_auth_console -q`
  - Result: `5 passed`.
- Live browser smoke:
  - Frontend: `http://127.0.0.1:5174`
  - Backend: `http://127.0.0.1:8002`
  - Command: `python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token admin-secret-token --json-out var\agriguard-admin-routes-redaction-2026-07-06.json --screenshot-dir var\agriguard-admin-routes-redaction-2026-07-06 --timeout-ms 30000`
  - Result: `admin routes browser smoke pass`.
- Redaction probe:
  - Operator token present: `False`.
  - JSON redaction marker count: `5`.
  - Raw verify route matches: `0`.
  - Raw `Token...State` table-token hints: `0`.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-admin-routes-redaction-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Admin routes browser smoke evidence now avoids storing raw QR token routes or token-table prefixes. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
