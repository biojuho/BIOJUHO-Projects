# AutoResearch Loop - AgriGuard Postgres Loopback Port

Date: 2026-07-04
App: AgriGuard
Cycle: Compose database exposure hardening

## Baseline

The AgriGuard compose file published Postgres on every host interface:

`5432:5432`

Risk:

- Local and staging hosts could expose the database port on the LAN or public network interface.
- The public request path already goes through edge nginx; direct external database access is not required for the app stack.

## Variant

Bound the Postgres host port to loopback while preserving local operator access:

`127.0.0.1:5432:5432`

Added config coverage in `test_cors_origins.py` so the database port cannot return to all-interface binding.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-postgres-loopback-port"`
  - Result: 14 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass
- `docker compose -f apps/AgriGuard/docker-compose.yml config | Select-String -Pattern 'host_ip|published: "5432"|target: 5432'`
  - Rendered Postgres port includes `host_ip: 127.0.0.1`.

## Decision

Adopt loopback-only Postgres publishing. Operators keep local database access, while the compose stack avoids exposing the database on external host interfaces by default.
