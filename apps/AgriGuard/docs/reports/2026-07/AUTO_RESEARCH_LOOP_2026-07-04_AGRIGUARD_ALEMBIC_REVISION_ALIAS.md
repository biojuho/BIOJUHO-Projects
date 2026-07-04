# AutoResearch Loop - AgriGuard Alembic Revision Alias

## Objective

Preserve migration compatibility after shortening AgriGuard Alembic revision
ids for Postgres. The previous loop fixed live Postgres startup, but databases
that had already recorded the old long ids could later fail with an unknown
revision before `upgrade head`.

## Scope and Owned Paths

- `apps/AgriGuard/backend/scripts/run_migrations.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`
- This cycle report.

## External Sources Checked

- Alembic tutorial: migration commands read the database's version table before
  calculating the upgrade path. Source:
  https://alembic.sqlalchemy.org/en/latest/tutorial.html
- `Veritas-7/autoresearch-skill-system` latest observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis and Decision Rule

- Baseline: leave the shortened revision ids without a compatibility bridge.
- Variant: rewrite known deprecated AgriGuard revision ids in
  `alembic_version` to their shortened replacements before calling Alembic.
- Primary KPI: databases stamped at the old ids can be normalized
  idempotently.
- Guardrails: fresh migration smoke still upgrades to head, all revision ids
  still fit the 32-character Postgres/Alembic version column, Docker startup
  stays healthy, and the aggregate browser suite still passes.

## Baseline Risk

The prior fix changed active revision ids from
`0005_add_qr_scan_event_kpi_indexes` and
`0006_add_sensor_device_owner_scope` to `0005_qr_kpi_indexes` and
`0006_sensor_owner_scope`. That is required for Postgres' default Alembic
version column, but an already-stamped local database could still contain the
old long value.

## Variant Evidence

- Added `DEPRECATED_REVISION_ALIASES` to `run_migrations.py`.
- Added `_rewrite_deprecated_revision_aliases()` using SQLAlchemy transaction
  scope before `command.upgrade(config, "head")`.
- The rewrite is a narrow allow-list for the two known AgriGuard ids and is a
  no-op when `alembic_version` is missing or already normalized.
- Added a regression test that seeds old ids in SQLite and verifies they are
  rewritten to the active ids.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_smoke.py::test_run_migrations_script_applies_head_revision apps/AgriGuard/backend/tests/test_smoke.py::test_alembic_revision_ids_fit_postgres_version_column apps/AgriGuard/backend/tests/test_smoke.py::test_run_migrations_rewrites_deprecated_revision_aliases -q
```

Result: `3 passed in 9.71s`.

```powershell
docker compose -f apps/AgriGuard/docker-compose.yml up -d --no-deps --build --force-recreate backend
```

Result: backend rebuilt and started with `State=running`, `Health=healthy`;
migration logs reported `Alembic migrations applied successfully`.

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-migration-alias.json --output-dir var\agriguard-browser-smoke-suite-migration-alias --timeout-ms 30000
```

Result: `passed=5`, `failed=0`, `checks_passed=121`,
`checks_failed=0`, `prechecks_passed=1`, `prechecks_failed=0`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-alembic-revision-alias.json
```

Result: `passed=5`, `failed=0`, `total=5`.

## Decision

Adopt the alias rewrite. It keeps the Postgres-safe shortened ids while
protecting previously stamped local databases from an avoidable Alembic
resolution failure.

## Next Cycle

Commit the owned patch, push, then continue with the next launch-hardening gap.
