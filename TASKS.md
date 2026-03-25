# Task Board

**Last Updated**: 2026-03-25
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

### P1 - Important
- [ ] **AgriGuard sensor_readings resync investigation**
  - **Description**: Latest QC rerun on 2026-03-25 failed the row-count gate because `sensor_readings` drift exceeded the allowed tolerance.
  - **Observed state**: PostgreSQL has `14,102` rows, the archived SQLite snapshot has `14,696`, and the current backend SQLite file has `14,782`.
  - **Next step**: Identify what is still writing to `AgriGuard/backend/agriguard.db`, decide whether PostgreSQL needs a controlled backfill, and rerun `qc_postgres_migration.py`.
  - **Files**: `AgriGuard/backend/scripts/qc_postgres_migration.py`, `AgriGuard/backend/agriguard.db`, `AgriGuard/backend/agriguard.db.archived_20260325`

---

## IN_PROGRESS

*No tasks in progress*

---

## DONE (Last 7 Days)

### 2026-03-25
- [x] **AgriGuard PostgreSQL QC snapshot documented**
  - **Result**: Root-safe QC script and written QC report added for the initial cutover validation snapshot.
  - **Files**: `AgriGuard/POSTGRES_MIGRATION_QC_REPORT.md`, `AgriGuard/backend/scripts/qc_postgres_migration.py`

- [x] **AgriGuard SQLite snapshot archived**
  - **Result**: Snapshot saved as `AgriGuard/backend/agriguard.db.archived_20260325` for later comparison during cutover monitoring.
  - **Note**: Follow-up investigation is still open because the latest QC rerun exceeded the `sensor_readings` drift tolerance.

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

- **Total Active Tasks**: 1
- **In Progress**: 0
- **Completed (7 days)**: 9+
- **Workspace Smoke**: 15/15 passed
- **AgriGuard QC**: latest rerun is 4/5 due to `sensor_readings` drift beyond tolerance

---

**Note for agents**: Do not mark the AgriGuard migration fully closed until the `sensor_readings` gap is explained or reconciled. Do not rerun the live migration into a populated target without an intentional `--truncate` plan.
