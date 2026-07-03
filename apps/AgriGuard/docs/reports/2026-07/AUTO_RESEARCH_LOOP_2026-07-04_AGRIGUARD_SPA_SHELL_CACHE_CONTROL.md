# AutoResearch Loop - AgriGuard SPA Shell Cache Control

Date: 2026-07-04
App: AgriGuard
Cycle: Frontend deploy freshness hardening

## Baseline

The frontend nginx config cached hashed static assets for one year, but the SPA fallback route did not set an explicit cache policy for `index.html`.

Risk:

- Browsers can heuristically cache the app shell.
- A deployment can publish new hashed assets while some users keep an older shell that points at stale asset names.

## Variant

Added a no-cache policy to the SPA fallback:

`add_header Cache-Control "no-cache" always;`

Because nginx `add_header` directives are not inherited into a location that defines its own headers, the baseline security headers are duplicated in the SPA fallback block.

Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-spa-shell-cache-control"`
  - Result: 21 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt explicit no-cache behavior for the SPA shell. Hashed assets remain long-cacheable, while the app entrypoint is refreshed on navigation after deploys.
