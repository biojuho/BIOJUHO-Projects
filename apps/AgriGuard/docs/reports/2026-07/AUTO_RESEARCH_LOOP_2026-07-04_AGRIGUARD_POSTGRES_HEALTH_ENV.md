# AutoResearch Loop - AgriGuard Postgres Health Env

Date: 2026-07-04
App: AgriGuard
Cycle: Compose database readiness hardening

## Baseline

The compose Postgres service supported configurable database identity:

- `POSTGRES_USER: ${AGRIGUARD_DB_USER:-agriguard}`
- `POSTGRES_DB: ${AGRIGUARD_DB_NAME:-agriguard}`

The healthcheck still probed the hard-coded default identity:

`pg_isready -U agriguard -d agriguard`

Risk:

- Deployments that override `AGRIGUARD_DB_USER` or `AGRIGUARD_DB_NAME` can start a valid database but fail the readiness gate.
- Backend startup remains blocked behind a false-negative Postgres health state.

## Variant

Changed the healthcheck to use the container environment values that Postgres already receives:

`pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}`

Added config coverage in `test_cors_origins.py` so the hard-coded probe cannot return.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-postgres-health-env"`
  - Result: 12 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the env-aware Postgres healthcheck. Compose readiness now tracks the database identity selected for the deployment instead of only the default local identity.
