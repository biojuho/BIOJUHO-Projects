# Task Board

**Last Updated**: 2026-03-25
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

*No tasks in TODO*

---

## IN_PROGRESS

*No tasks in progress*

---

## DONE (Last 7 Days)

### 2026-03-25
- [x] **AgriGuard sensor_readings resync investigation completed**
  - **Root cause**: A long-running local `python -m uvicorn main:app --reload --port 8002` listener imported `database.py` before `.env` was loaded, so it silently fell back to SQLite and kept appending simulated `sensor_readings`.
  - **Fix**: Backend entrypoints now load `AgriGuard/backend/.env` consistently through `AgriGuard/backend/env_loader.py`.
  - **Resync**: PostgreSQL was intentionally rebuilt from `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` with `--truncate`.
  - **Validation**: `qc_postgres_migration.py` passed `5/5`, `agriguard-backend` is healthy on port `8002`, and the frozen SQLite snapshot timestamp remains unchanged while live sensor writes continue in PostgreSQL.

- [x] **AgriGuard backend container startup fixed**
  - **Root cause**: `main.py` assumed `Path(__file__).resolve().parents[2]`, which crashes inside the Docker image layout.
  - **Fix**: Observability path discovery now scans available parents safely before extending `sys.path`.
  - **Validation**: `docker compose -f AgriGuard/docker-compose.yml up -d backend --build` produced a healthy backend container.

- [x] **AgriGuard backend env loading hardened**
  - **Result**: Local backend entrypoints now load `backend/.env` before DB initialization, preventing accidental SQLite fallback during import order.
  - **Validation**: `python -m pytest AgriGuard/backend/tests/test_database_config.py AgriGuard/backend/tests/test_env_loading.py -q`

- [x] **Content Intelligence Engine v2.0 upgrade**
  - **Result**: Content Intelligence workspace updates completed earlier on 2026-03-25.

- [x] **AgriGuard PostgreSQL QC snapshot documented**
  - **Result**: Root-safe QC script and written QC report added for the initial cutover validation snapshot.
  - **Files**: `AgriGuard/POSTGRES_MIGRATION_QC_REPORT.md`, `AgriGuard/backend/scripts/qc_postgres_migration.py`

- [x] **AgriGuard SQLite snapshot archived**
  - **Result**: Snapshot saved as `AgriGuard/backend/agriguard.db.archived_20260325` for later comparison during cutover monitoring.

- [x] **AgriGuard PostgreSQL benchmark completed**
  - **Result**: SQLite vs PostgreSQL benchmark captured in `AgriGuard/BENCHMARK_RESULTS.md`
  - **Validation**: Benchmark script ran successfully against local PostgreSQL

- [x] **AgriGuard backend switched to PostgreSQL configuration**
  - **Result**: `AgriGuard/backend/.env` now points to PostgreSQL
  - **Validation**: Docker PostgreSQL healthy, Alembic revision `0001` present

- [x] **AgriGuard migration QC script hardened**
  - **Result**: QC script now resolves the SQLite path relative to the backend directory and accepts configurable PostgreSQL settings
  - **Validation**: QC passes from the repository root

- [x] **GetDayTrends package import compatibility restored**
  - **Result**: Root-package imports and timeout propagation verified
  - **Validation**: targeted tests pass

- [x] **Workspace package runner and smoke retry added**
  - **Result**: root `npm run *:all` commands now walk package scripts directly, and transient Vitest worker failures retry once
  - **Validation**: `npm run lint:all`, workspace smoke tests

### 2026-03-24
- [x] **GetDayTrends modular refactoring**
  - **Validation**: 435 passed, 4 skipped, 1 deselected

- [x] **AgriGuard PostgreSQL Week 1-2**
  - **Result**: Alembic setup, Docker validation, PostgreSQL smoke checks

- [x] **Workspace QC recovery + NotebookLM auth**
  - **Result**: workspace smoke checks passed

---

## Board Statistics

- **Total Active Tasks**: 0
- **In Progress**: 0
- **Completed (7 days)**: 12+
- **Workspace Smoke**: 15/15 passed
- **AgriGuard QC**: frozen resync snapshot passes `5/5`; live PostgreSQL writes resumed after cutover

---

**Note for agents**: AgriGuard cutover is now reconciled. Use `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` as the preserved SQLite evidence snapshot, not as a live source.
