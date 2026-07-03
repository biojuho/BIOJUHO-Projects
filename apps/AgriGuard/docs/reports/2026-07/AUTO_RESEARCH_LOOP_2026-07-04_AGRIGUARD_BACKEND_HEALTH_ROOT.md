# AutoResearch Loop - AgriGuard Backend Health Root

Date: 2026-07-04
App: AgriGuard
Cycle: Backend container readiness hardening

## Baseline

The backend compose healthcheck probed FastAPI's generated documentation UI:

`http://localhost:8002/docs`

Risk:

- Container readiness depended on the docs UI remaining enabled.
- The health probe tested a documentation surface instead of the application API surface used by routing and proxy readiness.

## Variant

Changed the backend container healthcheck to probe the API root route:

`http://localhost:8002/`

Added config coverage in `test_cors_origins.py` so the compose healthcheck cannot drift back to `/docs`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-backend-health-root"`
  - Result: 13 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the API-root backend healthcheck. Compose readiness now depends on the application route instead of the generated documentation UI.
