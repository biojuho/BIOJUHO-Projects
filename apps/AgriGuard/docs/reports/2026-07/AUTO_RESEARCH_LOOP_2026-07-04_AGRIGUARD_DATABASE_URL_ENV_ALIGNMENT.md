# AutoResearch Loop - AgriGuard Database URL Env Alignment

Date: 2026-07-04
App: AgriGuard
Cycle: Compose database credential alignment

## Baseline

The compose Postgres service reads database identity from `AGRIGUARD_DB_USER`, `AGRIGUARD_DB_PASSWORD`, and `AGRIGUARD_DB_NAME`, including values from the app `.env`.

The backend fallback `DATABASE_URL` stayed hard-coded:

`postgresql://agriguard:agriguard_secret@postgres:5432/agriguard`

The rendered local compose config showed the mismatch:

- `POSTGRES_PASSWORD: agriguard_dev_password`
- `DATABASE_URL: postgresql://agriguard:agriguard_secret@postgres:5432/agriguard`

Risk:

- The database container can start with one password while the backend tries another.
- Operators who override `AGRIGUARD_DB_USER`, `AGRIGUARD_DB_PASSWORD`, or `AGRIGUARD_DB_NAME` must also remember to duplicate the full URL override.

## Variant

Changed the backend fallback URL to derive from the same compose variables used by Postgres:

`DATABASE_URL=${AGRIGUARD_DATABASE_URL:-postgresql://${AGRIGUARD_DB_USER:-agriguard}:${AGRIGUARD_DB_PASSWORD:-agriguard_secret}@postgres:5432/${AGRIGUARD_DB_NAME:-agriguard}}`

`AGRIGUARD_DATABASE_URL` remains the explicit full-URL override.

Added config coverage in `test_cors_origins.py` so the hard-coded database URL cannot return.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-db-url-env-alignment"`
  - Result: 13 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass
- `docker compose -f apps/AgriGuard/docker-compose.yml config | Select-String -Pattern 'POSTGRES_PASSWORD|DATABASE_URL'`
  - Rendered backend `DATABASE_URL` now uses the same `AGRIGUARD_DB_PASSWORD` value as the Postgres service.
- `$env:AGRIGUARD_DATABASE_URL='postgresql://override_user:override_pass@override-host:5432/override_db'; docker compose -f apps/AgriGuard/docker-compose.yml config | Select-String -Pattern 'DATABASE_URL'`
  - Rendered backend `DATABASE_URL` preserves the explicit full-URL override.

## Decision

Adopt the env-aligned backend database URL fallback. Compose now keeps Postgres credentials and backend connection credentials in one variable family unless a full `AGRIGUARD_DATABASE_URL` override is explicitly supplied.
