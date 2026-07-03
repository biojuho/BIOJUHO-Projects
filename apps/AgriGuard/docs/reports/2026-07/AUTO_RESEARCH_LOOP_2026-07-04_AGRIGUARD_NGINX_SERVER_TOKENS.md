# AgriGuard AutoResearch Loop - nginx server token hardening

Date: 2026-07-04

## Source-backed observation

The launch nginx configs had recently gained baseline browser security headers, but neither the SPA container nginx config nor the edge reverse-proxy nginx config disabled nginx version disclosure through `server_tokens`.

## Adopted variant

- Added `server_tokens off;` to `apps/AgriGuard/frontend/nginx.conf`.
- Added `server_tokens off;` to `apps/AgriGuard/nginx/nginx.conf`.
- Added a focused config regression test to keep both launch nginx configs aligned.

## Verification

- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-nginx-server-tokens"` (`22 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
