# AutoResearch Loop - AgriGuard Compose Edge Healthcheck

Date: 2026-07-04
App: AgriGuard
Cycle: Compose edge readiness hardening

## Baseline

The compose stack made the edge nginx service wait for healthy backend and frontend dependencies, but the edge nginx container itself had no healthcheck.

Risk:

- Compose could report the edge service as started even when nginx was not yet ready to serve requests.
- Operators and CI could not distinguish a running-but-unready edge container from a ready one through compose health state.

## Variant

Added an edge nginx healthcheck using the same local HTTP probe as the frontend container:

- `wget --no-verbose --tries=1 --spider http://localhost/ || exit 1`
- `interval: 30s`
- `timeout: 10s`
- `retries: 3`
- `start_period: 10s`

Updated config coverage so `test_cors_origins.py` requires both frontend and edge nginx compose health probes.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-compose-edge-health"`
  - Result: 11 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the edge nginx healthcheck. The compose stack now exposes health state for frontend, backend dependency readiness, and the public edge service.
