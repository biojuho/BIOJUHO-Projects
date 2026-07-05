# Auto Research Loop - AgriGuard QR Screenshot Masking

Date: 2026-07-06

## Source Basis

- OWASP logging and secrets-management guidance supports excluding bearer-like tokens and sensitive operational identifiers from durable operational artifacts.
- The admin QR-token and product-detail browser smokes write PNG screenshots as launch evidence. JSON redaction alone is insufficient if the screenshot still visibly contains public QR URLs, token prefixes, or a scannable QR graphic.

## Change

- Added screenshot masking to `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`.
  - Before PNG capture, public verify route text is replaced with `<redacted-public-qr-token>`.
  - QR token table prefix cells are replaced with `<redacted-public-qr-token>`.
- Added screenshot masking to `apps/AgriGuard/scripts/product_detail_browser_smoke.py`.
  - Before PNG capture, public verify route text is replaced with `<redacted-public-qr-token>`.
  - The product verification QR graphic is blurred and dimmed in screenshot evidence.
- Added focused unit coverage for both masking hooks.

## Verification

- Focused unit checks:
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_masks_public_qr_screenshot_artifacts apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_uses_viewport_screenshots_for_fixed_nav apps\AgriGuard\backend\tests\test_smoke.py::test_admin_routes_browser_smoke_redacts_public_qr_tokens_from_report -q`
  - Result: `3 passed`.
  - `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_masks_public_qr_screenshot_artifacts apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_redacts_public_qr_tokens_from_report apps\AgriGuard\backend\tests\test_smoke.py::test_product_detail_browser_smoke_uses_phone_viewport_for_mobile_default -q`
  - Result: `3 passed`.
- Live browser smokes:
  - `python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token screenshot-mask-admin-token --json-out var\agriguard-admin-routes-screenshot-mask-2026-07-06.json --screenshot-dir var\agriguard-admin-routes-screenshot-mask-2026-07-06 --timeout-ms 30000`
  - Result: `admin routes browser smoke pass`.
  - `python apps\AgriGuard\scripts\product_detail_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token screenshot-mask-detail-token --json-out var\agriguard-product-detail-screenshot-mask-2026-07-06.json --screenshot-dir var\agriguard-product-detail-screenshot-mask-2026-07-06 --timeout-ms 30000`
  - Result: `product detail browser smoke pass`.
- JSON leak probe:
  - Admin operator token present: `False`; redaction markers: `5`; raw verify route matches: `0`; raw `Token...State` hints: `0`.
  - Product-detail operator token present: `False`; redaction markers: `5`; raw verify route matches: `0`; raw `Token...State` hints: `0`.
- Screenshot visual inspection:
  - `var\agriguard-admin-routes-screenshot-mask-2026-07-06\qr-tokens.png` shows redacted QR label URL and token prefix text.
  - `var\agriguard-product-detail-screenshot-mask-2026-07-06\product-detail-initial.png` shows a blurred QR graphic and redacted visible QR URL.
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-screenshot-mask-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

Admin and product-detail screenshot evidence now masks public QR token material before PNG capture. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
