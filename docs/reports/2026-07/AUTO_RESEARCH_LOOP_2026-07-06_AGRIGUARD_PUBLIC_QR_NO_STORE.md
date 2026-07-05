# AutoResearch Loop - AgriGuard Public QR No-Store Cache Gate

Date: 2026-07-06

## Source basis

- AutoResearch/Karpathy source guard refreshed against `https://github.com/Veritas-7/autoresearch-skill-system.git` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- MDN documents `Cache-Control: no-store` as a response directive telling private and shared caches not to store the response: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control
- OWASP Cheat Sheet Series on GitHub recommends `no-store` for sensitive/dynamic data that should not be cached: https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/HTTP_Headers_Cheat_Sheet.md

## Baseline finding

The public QR verification route is a `GET` endpoint that returns dynamic trust evidence:

- QR token validity can change after revocation or expiry.
- Product trust status can change after recall, route, or temperature evidence updates.
- The response includes public traceability evidence intended to reflect the current verification state.

Before this loop the route did not set cache-control headers, so browsers, shared proxies, or intermediary caches had no route-level instruction to avoid storing stale valid/invalid QR verification results.

## Adopted changes

- Added `PUBLIC_VERIFY_CACHE_HEADERS` to `routers/qr_verify.py`.
- Set these headers on every `/api/qr/{qr_token}/verify` response:
  - `Cache-Control: no-store`
  - `Pragma: no-cache`
  - `Expires: 0`
- Added `test_public_qr_verify_cache_headers.py`, an isolated FastAPI/TestClient gate that verifies the route returns no-store headers and still records the invalid-token analytics event.
- Left the broader dirty `test_product_and_qr_routes.py` file unstaged; it was used for verification only.

## Evidence

- `python -m pytest apps\AgriGuard\backend\tests\test_public_qr_verify_cache_headers.py -q`: 1 passed.
- `python -m pytest apps\AgriGuard\backend\tests\test_product_and_qr_routes.py -q`: 41 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`: passed=5, failed=0, total=5.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-public-qr-cache-2026-07-06.json`: status `blocked`, blocker_class `preflight_blocked`.

## Remaining blocker

Launch remains externally blocked on operator-provided Firebase Admin credentials:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Public QR cache-control is local and green. Guarded launch should still fail closed until the operator supplies the real service-account file outside the repository and reruns strict preflight.
