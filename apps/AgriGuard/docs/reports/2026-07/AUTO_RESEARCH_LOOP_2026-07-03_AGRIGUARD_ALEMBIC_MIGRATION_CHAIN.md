# AutoResearch Loop: AgriGuard Alembic Migration Chain

Date: 2026-07-03

## Scope

Closed a launch-readiness gap where committed runtime models had advanced past the tracked Alembic history:

- Added `0003_add_qr_tokens.py` for the durable QR token table.
- Added `0004_add_sensor_devices.py` for the sensor device registry.
- Added `0005_add_qr_scan_event_kpi_indexes.py` for QR KPI query indexes.
- Added `0006_add_sensor_device_owner_scope.py` for sensor ownership scoping.
- Strengthened `test_run_migrations_script_applies_head_revision` so a fresh database must upgrade to `0006_add_sensor_device_owner_scope` and expose the launch-critical tables/indexes.

## Source-Backed Rationale

Alembic's official tutorial describes revision files as a graph ordered by `revision` and `down_revision`, with `upgrade()` applying schema changes and `downgrade()` reversing them. Because `0005` depends on `0004`, committing only the QR KPI index migration would leave the repository with an invalid migration graph. Source: https://alembic.sqlalchemy.org/en/latest/tutorial.html

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with alembic>=1.14.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests/test_smoke.py::test_run_migrations_script_applies_head_revision -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-alembic"`: 1 passed.
- `python -m py_compile backend/alembic/versions/0003_add_qr_tokens.py backend/alembic/versions/0004_add_sensor_devices.py backend/alembic/versions/0005_add_qr_scan_event_kpi_indexes.py backend/alembic/versions/0006_add_sensor_device_owner_scope.py backend/tests/test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with alembic>=1.14.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests/test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-smoke-migrations"`: 6 passed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-migrations.json`: 5/5 passed, including 385 backend tests and 26 contract tests.

## Notes

- This loop has no UI change, so browser smoke was not rerun; the workspace smoke reran frontend lint/build and the full backend/contracts gates.
- The migration smoke uses `AUTO_CREATE_SCHEMA=0` for the migration runner proof so schema creation must come from Alembic, not SQLAlchemy metadata auto-create.
