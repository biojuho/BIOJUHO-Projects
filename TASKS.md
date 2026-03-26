# Task Board

**Last Updated**: 2026-03-26
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

*No tasks in TODO*

---

## IN_PROGRESS

*No tasks in progress*

---

## DONE (Last 7 Days)

### 2026-03-26
- [x] **Workspace QC completed**
  - **Result**: `python scripts/run_workspace_smoke.py --scope all --json-out smoke_report_qc_2026-03-26.json` completed successfully
  - **Validation**: Workspace smoke `15/15 PASS`

- [x] **Content Intelligence v2.0 QC completed**
  - **Result**: `content-intelligence` v2.0 changes verified after the publishing and GDT bridge updates
  - **Validation**: `python -m pytest content-intelligence/tests/test_smoke.py -q` -> `31 passed`
  - **Validation**: `python -X utf8 content-intelligence/main.py --dry-run` -> OK

- [x] **Docker dev environment hardening and live QC**
  - **Result**: Fixed the Mosquitto healthcheck interpolation bug, added starter Prometheus/Grafana config, and hardened `scripts/setup_dev_environment.ps1`
  - **Validation**: `docker compose -f docker-compose.dev.yml --profile monitoring config --no-interpolate`
  - **Validation**: `powershell -ExecutionPolicy Bypass -File scripts/setup_dev_environment.ps1 -Status`
  - **Live checks**: `docker compose -f docker-compose.dev.yml --profile monitoring up -d prometheus grafana`
  - **Live checks**: `http://localhost:9090/-/ready` -> `200`
  - **Live checks**: `http://localhost:3000/login` -> `200`
  - **Note**: The monitoring containers were intentionally brought back down after QC

- [x] **Unified AI Dashboard v1.0 verified**
  - **Result**: Dashboard API and frontend were verified end-to-end in the earlier 2026-03-26 session
  - **QC**: `.agent/qa-reports/2026-03-26-dashboard-v1.md`

- [x] **Tech debt inventory enhancement**
  - **Result**: Enhanced classification logic to eliminate false P1 positives
  - **Changes**: Documents default to P3, excluded .agent/.sessions/ directories
  - **Outcome**: P1 reduced from 6 to 0 (code-related)

- [x] **GetDayTrends QA and prompts migration completed**
  - **Result**: Verified migrations already complete; added backward-compatible wrappers
  - **Files**: `generation/audit.py`, `generation/prompts.py` now re-export from `content_qa.py` and `prompt_builder.py`

- [x] **Canva MCP integration completed**
  - **Result**: Complete rewrite from 38-line skeleton to 223-line functional MCP bridge
  - **Features**: CanvaMCPClient class, JSON-RPC 2.0 protocol, async design creation, graceful fallback
  - **File**: `getdaytrends/canva.py`
  - **Status**: Last P2 tech debt item resolved

### 2026-03-25
- [x] **AgriGuard sensor_readings resync investigation completed**
  - **Root cause**: A long-running local `python -m uvicorn main:app --reload --port 8002` listener imported `database.py` before `.env` was loaded, so it silently fell back to SQLite and kept appending simulated `sensor_readings`
  - **Fix**: Backend entrypoints now load `AgriGuard/backend/.env` consistently through `AgriGuard/backend/env_loader.py`
  - **Resync**: PostgreSQL was intentionally rebuilt from `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` with `--truncate`
  - **Validation**: `qc_postgres_migration.py` passed `5/5`

- [x] **AgriGuard backend container startup fixed**
  - **Root cause**: `main.py` assumed `Path(__file__).resolve().parents[2]`, which crashes inside the Docker image layout
  - **Fix**: Observability path discovery now scans available parents safely before extending `sys.path`

- [x] **AgriGuard backend env loading hardened**
  - **Result**: Local backend entrypoints now load `backend/.env` before DB initialization, preventing accidental SQLite fallback during import order
  - **Validation**: `python -m pytest AgriGuard/backend/tests/test_database_config.py AgriGuard/backend/tests/test_env_loading.py -q`

- [x] **Content Intelligence Engine v2.0 upgrade**
  - **Result**: Content Intelligence workspace updates completed earlier on 2026-03-25

- [x] **AgriGuard PostgreSQL QC snapshot documented**
  - **Result**: Root-safe QC script and written QC report added for the initial cutover validation snapshot
  - **Files**: `AgriGuard/POSTGRES_MIGRATION_QC_REPORT.md`, `AgriGuard/backend/scripts/qc_postgres_migration.py`

- [x] **AgriGuard SQLite snapshot archived**
  - **Result**: Snapshot saved as `AgriGuard/backend/agriguard.db.archived_20260325`

- [x] **AgriGuard PostgreSQL benchmark completed**
  - **Result**: SQLite vs PostgreSQL benchmark captured in `AgriGuard/BENCHMARK_RESULTS.md`

- [x] **AgriGuard backend switched to PostgreSQL configuration**
  - **Result**: `AgriGuard/backend/.env` now points to PostgreSQL

- [x] **AgriGuard migration QC script hardened**
  - **Result**: QC script now resolves the SQLite path relative to the backend directory and accepts configurable PostgreSQL settings

- [x] **GetDayTrends package import compatibility restored**
  - **Result**: Root-package imports and timeout propagation verified

- [x] **Workspace package runner and smoke retry added**
  - **Result**: Root `npm run *:all` commands now walk package scripts directly, and transient Vitest worker failures retry once

### 2026-03-24
- [x] **GetDayTrends modular refactoring**
  - **Validation**: `435 passed, 4 skipped, 1 deselected`

- [x] **AgriGuard PostgreSQL Week 1-2**
  - **Result**: Alembic setup, Docker validation, PostgreSQL smoke checks

- [x] **Workspace QC recovery + NotebookLM auth**
  - **Result**: workspace smoke checks passed

---

## Board Statistics

- **Total Active Tasks**: 0
- **In Progress**: 0
- **Completed (7 days)**: 17+
- **Workspace Smoke**: 15/15 passed
- **CIE v2 Smoke**: 31/31 passed
- **Dashboard QA/QC**: verified (6 auto-fixes)
- **Dashboard Status**: Backend (http://localhost:8080) + Frontend (http://localhost:5173) running
- **AgriGuard QC**: frozen resync snapshot passes `5/5`; live PostgreSQL writes resumed after cutover
- **Tech Debt**: P0=0, P1=0 (code), P2=0, P3=278+ (all non-critical)

---

**Note for agents**: AgriGuard cutover is reconciled. Use `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` as the preserved SQLite evidence snapshot, not as a live source.
