# AutoResearch Loop - AgriGuard Nginx Security Headers

Date: 2026-07-04
App: AgriGuard
Cycle: HTTP response hardening

## Baseline

The frontend nginx and edge nginx configs did not set baseline browser security headers.

Risk:

- Responses lacked MIME-sniffing protection.
- The app did not explicitly opt out of being framed by another site.
- Browser referrer behavior was left to defaults.

## Variant

Added low-risk response headers to both nginx configs:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

The frontend static-asset location already sets `Cache-Control`, so the same security headers are duplicated there to avoid nginx `add_header` inheritance gaps.

Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-nginx-security-headers"`
  - Result: 17 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass
- `Get-Command nginx -ErrorAction SilentlyContinue`
  - Status: no local nginx binary available; nginx syntax validation was not run in this environment.

## Decision

Adopt the baseline nginx security headers. The change avoids CSP and permissions-policy restrictions that could interfere with QR camera workflows, while still improving default browser hardening.
