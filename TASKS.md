# Task Board

**Last Updated**: 2026-03-25
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

### P3 - Follow-up
- [ ] **AgriGuard PostgreSQL cutover monitoring**
  - **Description**: Keep PostgreSQL as the primary database, re-run QC after the monitoring window, and archive the SQLite file once the system is stable.
  - **Current state**: `users`, `products`, `tracking_events`, and `certificates` match between SQLite and PostgreSQL. `sensor_readings` is allowed to drift during live ingestion and should stay within the QC tolerance window.
  - **Files**: `AgriGuard/backend/scripts/qc_postgres_migration.py`, `AgriGuard/BENCHMARK_RESULTS.md`, `AgriGuard/backend/.env`

---

## IN_PROGRESS

*No tasks in progress*

---

## DONE (Last 7 Days)

### 2026-03-25
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
- **Completed (7 days)**: 8+
- **Workspace Smoke**: 15/15 passed
- **AgriGuard QC**: 5/5 checks passed with tolerated live `sensor_readings` drift

---

**Note for agents**: Check the current PostgreSQL QC status before marking the AgriGuard migration fully closed. Do not rerun the live migration into a populated target without an intentional `--truncate` plan.
