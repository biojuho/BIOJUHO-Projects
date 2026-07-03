# AutoResearch Loop - AgriGuard Backend Loopback Port

Date: 2026-07-04
App: AgriGuard
Cycle: Compose API exposure hardening

## Baseline

The AgriGuard backend service published its API port on every host interface:

`8002:8002`

Risk:

- The backend API could be reachable directly from external host interfaces, bypassing the edge nginx entrypoint.
- Operators had two public HTTP paths to reason about: edge nginx and direct backend port.

## Variant

Bound the backend host port to loopback while preserving local diagnostics:

`127.0.0.1:8002:8002`

The edge nginx service still publishes ports `80` and `443` for the public app path.

Added config coverage in `test_cors_origins.py` so the backend API port cannot return to all-interface binding.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-backend-loopback-port"`
  - Result: 15 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass
- `docker compose -f apps/AgriGuard/docker-compose.yml config | Select-String -Pattern 'host_ip|published: "8002"|target: 8002'`
  - Rendered backend port includes `host_ip: 127.0.0.1`.

## Decision

Adopt loopback-only backend API publishing. Local operators can still inspect the backend directly, while normal users reach the app through edge nginx.
