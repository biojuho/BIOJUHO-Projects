# AutoResearch Loop: AgriGuard Unowned Sensor Audit

Date: 2026-07-03

## Scope

Added an operator audit/backfill tool for sensor devices that lack `owner_id` before tenant scoping or row-level-security rollout:

- Added `backend/scripts/report_unowned_sensor_devices.py`.
- Added report builders for unowned/active/disabled counts, zone counts, and sampled sensors.
- Added dry-run and apply paths for explicit sensor backfills or reviewed all-unowned backfills.
- Added JSON and Markdown output support.
- Added fail-closed CLI behavior for invalid plans and missing/unmigrated database schemas.
- Added focused tests for report counts, target validation, selected backfill, CLI output, and no-traceback missing-schema failure.

## Source-Backed Rationale

PostgreSQL row-level security policies filter row visibility by policy expressions and default to denying rows when no applicable policy exists. Before enabling tenant-scoped policies on sensor-backed data, legacy rows without an owner need to be audited or deliberately backfilled so ownership behavior is explicit. Source: https://www.postgresql.org/docs/current/ddl-rowsecurity.html

## Evidence

- `python -m py_compile backend/scripts/report_unowned_sensor_devices.py backend/tests/test_unowned_sensor_devices_script.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests/test_unowned_sensor_devices_script.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-unowned-sensors"`: 6 passed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-unowned-sensor-audit.json`: 5/5 passed, including 386 backend tests and 26 contract tests.
- Configured database read-only run: `python scripts/report_unowned_sensor_devices.py --json-out "D:\AI project\var\agriguard-unowned-sensors-report.json" --markdown-out "D:\AI project\var\agriguard-unowned-sensors-report.md" --limit 10`: exited 2 with `database schema is not ready` because `sensor_devices` does not exist in the configured PostgreSQL target.
- Temp SQLite fixture run wrote:
  - `D:\AI project\var\agriguard-unowned-sensors-fixture-report.json`
  - `D:\AI project\var\agriguard-unowned-sensors-fixture-report.md`

## Notes

- No production backfill was applied.
- The configured PostgreSQL target still needs the committed Alembic chain applied before this audit can inspect real sensor rows.
- The fixture proof kept `--apply` omitted, so the backfill block is a plan only.
