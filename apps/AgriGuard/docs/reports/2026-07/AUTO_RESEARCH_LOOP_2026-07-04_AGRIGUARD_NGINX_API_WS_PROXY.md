# AutoResearch Loop - AgriGuard Nginx API WebSocket Proxy

Date: 2026-07-04
App: AgriGuard
Cycle: Cold-chain WebSocket production proxy hardening

## Baseline

The frontend cold-chain dashboard opens the WebSocket at `/api/ws/iot`. Vite already proxies `/api` with `ws: true`, but the production nginx configs did not have a dedicated `/api/ws/` location with WebSocket upgrade headers.

Risk:

- `/api/ws/iot` could be handled by the normal REST `/api/` proxy.
- The backend would receive the stripped `/ws/iot` path, but without `Upgrade` and `Connection` headers required for WebSocket handoff.

## Variant

Added explicit `/api/ws/` locations before the normal `/api/` locations:

- `apps/AgriGuard/frontend/nginx.conf`
  - `/api/ws/` proxies to `http://backend:8002/ws/`
  - Adds `proxy_http_version 1.1`, `Upgrade`, `Connection`, and long read/send timeouts.
- `apps/AgriGuard/nginx/nginx.conf`
  - `/api/ws/` proxies to `http://backend/ws/`
  - Adds the same upgrade headers and long read/send timeouts.
- Added a config test that asserts both nginx configs strip `/api` for WebSocket traffic and include upgrade headers.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-nginx-ws-proxy"`
  - Result: 7 passed
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-nginx-api-ws-proxy.json`
  - Status: complete
  - Passed: 5/5
  - Failed: 0
  - Covered: frontend lint, frontend build, contracts compile, contracts tests, backend tests
- Attempted `nginx -t` through Docker for both configs.
  - Not completed because Docker CLI is installed but the Docker Desktop Linux engine is not running: `dockerDesktopLinuxEngine` pipe missing.
  - No local `nginx` binary was available.

## Decision

Adopt the explicit `/api/ws/` nginx proxy locations. This aligns production proxy behavior with the frontend's `/api/ws/iot` WebSocket URL and Vite's development proxy behavior.
