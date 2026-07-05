# Auto Research Loop - AgriGuard Product Detail Report Redaction

Date: 2026-07-06

## Source Basis

- OWASP logging and secrets-management guidance supports excluding bearer-like tokens and sensitive operational identifiers from durable logs and smoke-test artifacts.
- The product-detail browser smoke seeds a real product and captures QR label body-text samples. Persisted smoke JSON should prove the product detail route works without storing raw public QR token material.

## Change

- Added public QR report redaction helpers to `apps/AgriGuard/scripts/product_detail_browser_smoke.py`.
- The browser workflow still uses the real product QR value during the smoke, but persisted JSON now redacts:
  - `agri://verify/{token}` values
  - `/verify/{token}` route details
  - `/api/qr/{token}/verify` request or check metadata
- Added `test_product_detail_browser_smoke_redacts_public_qr_tokens_from_report`.

## Verification

- Focused unit checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_redacts_public_qr_tokens_from_report -q`
  - Result: `1 passed`.
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_uses_phone_viewport_for_mobile_default apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_tracks_mobile_first_viewport_targets apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_uses_operator_token_env -q`
  - Result: `3 passed`.
- Live browser smoke:
  - Frontend: `http://127.0.0.1:5174`
  - Backend: `http://127.0.0.1:8002`
  - Command: `python apps\AgriGuard\scripts\product_detail_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token detail-secret-token --json-out var\agriguard-product-detail-redaction-2026-07-06.json --screenshot-dir var\agriguard-product-detail-redaction-2026-07-06 --timeout-ms 30000`
  - Result: `product detail browser smoke pass`.
- Redaction probe:
  - Operator token present: `False`.
  - JSON redaction marker count: `5`.
  - Raw verify route matches: `0`.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-product-detail-redaction-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Product-detail browser smoke evidence now avoids storing raw public QR token routes or seeded QR prefixes. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
