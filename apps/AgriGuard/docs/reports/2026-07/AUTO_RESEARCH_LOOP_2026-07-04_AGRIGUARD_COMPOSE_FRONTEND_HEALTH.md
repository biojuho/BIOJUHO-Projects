# AutoResearch Loop - AgriGuard Compose Frontend Health Gate

Date: 2026-07-04
App: AgriGuard
Cycle: Compose startup dependency hardening

## Baseline

The AgriGuard compose stack made nginx wait for a healthy backend, but only waited for the frontend container to be started:

`frontend: condition: service_started`

Risk:

- nginx can start before the frontend nginx container is ready to serve the React app.
- First requests after deployment can hit a partially initialized frontend service.

## Variant

Added a frontend healthcheck and changed nginx to wait for frontend health:

- Frontend healthcheck: `wget --no-verbose --tries=1 --spider http://localhost/ || exit 1`
- `nginx.depends_on.frontend.condition`: `service_healthy`
- Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-compose-frontend-health"`
  - Result: 11 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the frontend health gate. Compose startup now waits for both backend and frontend readiness before starting the edge nginx service.
