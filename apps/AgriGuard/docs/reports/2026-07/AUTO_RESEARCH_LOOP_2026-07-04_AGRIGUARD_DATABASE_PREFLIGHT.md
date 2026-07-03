# AgriGuard AutoResearch Loop - database preflight

Date: 2026-07-04

## Source-backed observation

The backend direct runtime reads `DATABASE_URL`, while compose builds backend `DATABASE_URL` from `AGRIGUARD_DATABASE_URL` or the Postgres service credentials. The launch preflight previously rejected SQLite when a URL was present, but still allowed launch checks to pass without explicit database credentials, leaving compose on default Postgres credentials or direct startup on the backend SQLite fallback.

## Adopted variant

- Direct runtime preflight now validates only direct `DATABASE_URL`; `AGRIGUARD_DATABASE_URL` is treated as compose-only.
- Compose launch preflight requires either a PostgreSQL `AGRIGUARD_DATABASE_URL` with a non-placeholder password or a strong non-placeholder `AGRIGUARD_DB_PASSWORD`.
- Database URL validation now rejects non-PostgreSQL schemes, missing passwords, placeholder/default database passwords, and passwords shorter than 16 characters.
- The launch report records `database_password_source` and `database_password_min_length` without exposing secret values.
- The README launch checklist now calls out the database credential requirement.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-database-preflight"` (`43 passed`, 2 warnings)
- Pass: synthetic app-scoped launch env with `AGRIGUARD_DB_PASSWORD` wrote `var/agriguard-launch-env-preflight-database-pass.json` with status `pass`.
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`.
- Expected fail-closed: current strict preflight wrote `var/agriguard-launch-env-preflight-database-current.json` with status `fail` because app-scoped launch values are not fully set.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-database-docker-current.json` with the same missing app-scoped launch values plus unavailable Docker daemon. The database credential check found a configured `AGRIGUARD_DB_PASSWORD` source in this local env, so database credentials were not the current local blocker.
