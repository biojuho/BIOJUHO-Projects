# AgriGuard AutoResearch Loop - compose HTTPS port alignment

Date: 2026-07-04

## Source-backed observation

The launch compose file published `443:443`, but the edge nginx config only listens on port 80 and has no TLS certificate wiring. This made HTTPS appear available in compose while the container had no HTTPS listener.

## Adopted variant

- Removed the dead `443:443` publication from `apps/AgriGuard/docker-compose.yml`.
- Added a regression test that keeps compose from publishing HTTPS unless the edge nginx config has TLS listener/certificate configuration.

## Verification

- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-compose-https-port"` (`23 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
