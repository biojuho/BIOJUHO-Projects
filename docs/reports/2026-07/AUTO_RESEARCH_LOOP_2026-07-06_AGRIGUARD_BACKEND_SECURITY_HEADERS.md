# AutoResearch Loop - AgriGuard Backend Security Headers

Date: 2026-07-06

## Source basis

- AutoResearch/Karpathy source guard refreshed against `https://github.com/Veritas-7/autoresearch-skill-system.git` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- OWASP Cheat Sheet Series on GitHub recommends response headers such as `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`: https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/HTTP_Headers_Cheat_Sheet.md
- OWASP Secure Headers Project tracks HTTP security-header adoption and tooling: https://github.com/OWASP/www-project-secure-headers

## Baseline finding

AgriGuard nginx already set `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`, but FastAPI responses did not set the same baseline headers when reached directly or through a proxy path that does not preserve edge headers. The nginx configs also had no `Permissions-Policy`, leaving browser feature access unrestricted at the document edge.

Observed baseline probe:

- `TestClient(main.app).get("/")` returned `200` with rate-limit headers but no baseline security headers.

## Adopted changes

- Added `BASELINE_SECURITY_HEADERS` in `backend/main.py`.
- Added `security_headers_middleware` to set missing baseline headers on FastAPI responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(self), geolocation=(), microphone=()`
- Added backend response-header test coverage with `TestClient`.
- Extended frontend and edge nginx configs with the same `Permissions-Policy`, allowing the QR scanner camera only for same-origin app context and disabling geolocation/microphone.
- Kept CSP and HSTS out of this loop. CSP needs a separate inline-script/service-worker registration refactor, and HSTS should be enabled only when the operator-provided HTTPS/TLS edge is known.

## Evidence

- `python -m pytest apps\AgriGuard\backend\tests\test_cors_origins.py::test_nginx_configs_set_baseline_security_headers apps\AgriGuard\backend\tests\test_cors_origins.py::test_frontend_nginx_does_not_cache_spa_shell apps\AgriGuard\backend\tests\test_cors_origins.py::test_backend_sets_baseline_security_headers_on_api_responses -q`: 3 passed.
- `python -m pytest apps\AgriGuard\backend\tests\test_cors_origins.py apps\AgriGuard\backend\tests\test_auth_security.py -q`: 43 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`: passed=5, failed=0, total=5.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-security-headers-2026-07-06.json`: status `blocked`, blocker_class `preflight_blocked`.

## Remaining blocker

Launch remains externally blocked on operator-provided Firebase Admin credentials:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Security-header coverage is local and green. Guarded launch should still fail closed until the operator supplies the real service-account file outside the repository and reruns strict preflight.
