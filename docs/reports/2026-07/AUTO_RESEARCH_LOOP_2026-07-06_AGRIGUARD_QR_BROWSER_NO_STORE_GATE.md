# Auto Research Loop - AgriGuard QR Browser No-Store Gate

Date: 2026-07-06

## Source Basis

- OWASP HTTP header guidance and MDN Cache-Control guidance both support fail-closed handling for sensitive, user-specific, or integrity-sensitive responses.
- Public QR verification responses carry product trust state and scan analytics. The browser smoke now proves those API responses are not cacheable in the real public verification path.

## Change

- Extended `apps/AgriGuard/scripts/qr_path_browser_smoke.py` to capture Playwright response headers for public QR verify API calls.
- Added the `public_verify_api_responses_no_store` browser-smoke check. It requires at least two public verify API responses and requires every captured response to include:
  - `Cache-Control: no-store`
  - `Pragma: no-cache`
  - `Expires: 0`
- Hardened seeded QR token extraction for `verify/<token>` and duplicate `/verify/verify/<token>` shapes so setup mistakes fail less opaquely.
- Added unit coverage in `apps/AgriGuard/backend/tests/test_smoke.py` for public verify API response matching, no-store header validation, and token extraction normalization.

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py::test_qr_path_browser_smoke_extracts_public_verify_tokens apps\AgriGuard\backend\tests\test_smoke.py::test_qr_path_browser_smoke_tracks_public_verify_cache_headers -q`
  - Result: `2 passed`.
- Stale existing stack check:
  - `python apps\AgriGuard\scripts\qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-qr-path-no-store-browser-2026-07-06.json --screenshot-dir var\agriguard-qr-path-no-store-browser-2026-07-06 --timeout-ms 30000`
  - Result: `26/27 PASS`; the new no-store gate failed because the existing 8002 stack was stale and returned empty cache headers.
- Fresh isolated stack check:
  - Backend: `http://127.0.0.1:8003`
  - Frontend: `http://127.0.0.1:5198`
  - Corrected `PUBLIC_VERIFY_BASE_URL=http://127.0.0.1:5198`
  - `python apps\AgriGuard\scripts\qr_path_browser_smoke.py --base-url http://127.0.0.1:5198 --api-url http://127.0.0.1:8003 --operator-token browser-smoke-token --json-out var\agriguard-qr-path-no-store-browser-fresh-2026-07-06.json --screenshot-dir var\agriguard-qr-path-no-store-browser-fresh-2026-07-06 --timeout-ms 30000`
  - Result: `27/27 PASS`.
  - Captured four public verify API responses; all had `Cache-Control: no-store`, `Pragma: no-cache`, and `Expires: 0`.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-qr-browser-no-store-gate-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: not accepted as a pass. The runner exceeded the 3-minute tool timeout and left a low-CPU backend-test child. The exact smoke parent was stopped; no 8003/5198 temporary listeners remained.

## Current Launch Blocker

Local QR no-store browser evidence is green. Full guarded launch remains externally blocked until the operator provides a real `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` path outside the repository.
