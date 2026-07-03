# AgriGuard AutoResearch Loop - websocket forwarded protocol

Date: 2026-07-04

## Source-backed observation

The edge nginx `/ws/` proxy preserved websocket upgrade headers and client address metadata, but it did not forward the original scheme. The `/api/ws/`, `/api/`, and frontend proxy paths already set `X-Forwarded-Proto`.

## Adopted variant

- Added `proxy_set_header X-Forwarded-Proto $scheme;` to the edge nginx direct `/ws/` websocket block.
- Expanded nginx config tests so websocket proxy blocks must preserve the forwarded protocol metadata.

## Verification

- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-ws-forwarded-proto"` (`25 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
