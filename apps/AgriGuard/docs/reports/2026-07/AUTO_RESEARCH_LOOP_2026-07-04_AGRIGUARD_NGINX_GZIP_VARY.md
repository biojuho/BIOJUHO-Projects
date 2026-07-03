# AgriGuard AutoResearch Loop - nginx gzip vary header

Date: 2026-07-04

## Source-backed observation

The edge nginx config enabled gzip for text responses but did not set `gzip_vary on;`, so downstream caches could miss the `Vary: Accept-Encoding` signal for compressed response variants.

## Adopted variant

- Added `gzip_vary on;` beside the edge nginx gzip configuration.
- Added a focused static config test to keep gzip cache-safety enabled.

## Verification

- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-nginx-gzip-vary"` (`26 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
