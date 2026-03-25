# Task Board

**Last Updated**: 2026-03-25
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

*No tasks in TODO*

---

## IN_PROGRESS

- [ ] **Docker 개발 환경 라이브 검증**
  - **현재 상태**: `docker-compose.dev.yml` 정적 검증은 통과했고, `monitoring/` starter 설정과 `setup_dev_environment.ps1` 보강도 반영됨
  - **남은 확인**: Docker Desktop Linux engine이 정상 기동된 상태에서 `scripts/setup_dev_environment.ps1` 또는 `docker compose -f docker-compose.dev.yml up -d` 실구동 확인
  - **현재 블로커**: 이 세션에서는 `dockerDesktopLinuxEngine` named pipe를 찾지 못했고, 확인 결과 Windows `WslService`가 `DISABLED` 상태라 일반 권한 셸에서는 서비스를 시작할 수 없었음

---

## DONE (Last 7 Days)

### 2026-03-26
- [x] **Docker 개발 환경 구성 하드닝**
  - **Result**: `mosquitto` healthcheck의 Compose 변수 치환 버그를 수정했고, Prometheus/Grafana starter 설정 파일을 추가해 `monitoring` 프로필이 파일 누락 없이 검증되도록 정리함
  - **Script fix**: `scripts/setup_dev_environment.ps1`가 올바른 워크스페이스 루트를 사용하도록 수정했고, 외부 `docker` 명령 실패를 조기에 감지하도록 보강함
  - **Validation**: `docker compose -f docker-compose.dev.yml --profile monitoring config --no-interpolate`, `python -X utf8 content-intelligence/main.py --dry-run`, `python -m pytest content-intelligence/tests/test_smoke.py -q`

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
