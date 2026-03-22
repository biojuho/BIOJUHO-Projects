# Migrate AgriGuard from SQLite to PostgreSQL

**Labels**: `enhancement`, `high-priority`, `backend`, `database`
**Priority**: 🔥 **High** - 2주 내 완료

---

## Description

AgriGuard의 SQLite는 동시성 문제로 프로덕션 환경에서 적합하지 않습니다. PostgreSQL로 마이그레이션합니다.

---

## Current State

- **Database**: SQLite (`agriguard.db`)
- **ORM**: SQLAlchemy
- **Port**: 8002
- **Problem**: 동시 쓰기 작업 시 `database is locked` 에러 발생 가능

---

## Tasks

### Week 1: 환경 구축 및 마이그레이션 준비
- [ ] PostgreSQL Docker Compose 설정 추가
- [ ] Alembic 마이그레이션 도구 설정
- [ ] 초기 스키마 마이그레이션 스크립트 작성
- [ ] SQLAlchemy connection string 환경 변수화
- [ ] 병렬 테스트 환경 구축 (SQLite vs PostgreSQL)

### Week 2: 데이터 마이그레이션 및 테스트
- [ ] 데이터 마이그레이션 스크립트 작성
- [ ] 로컬 테스트 (Docker Compose 환경)
- [ ] 성능 벤치마크 (SQLite vs PostgreSQL)
- [ ] 동시성 테스트 (10+ concurrent writes)
- [ ] 롤백 계획 수립
- [ ] 문서 업데이트 (CLAUDE.md)

---

## Environment Variables

### Before
```env
DATABASE_URL=sqlite:///./agriguard.db
```

### After
```env
DATABASE_URL=postgresql://agriguard:${DB_PASSWORD}@localhost:5432/agriguard
DB_PASSWORD=secure_password_here
```

---

## Docker Compose Configuration

### `docker-compose.yml` 추가

```yaml
services:
  agriguard-db:
    image: postgres:16-alpine
    container_name: agriguard-postgres
    environment:
      POSTGRES_USER: agriguard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: agriguard
    ports:
      - "5432:5432"
    volumes:
      - agriguard-data:/var/lib/postgresql/data
      - ./AgriGuard/backend/migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agriguard"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  agriguard-data:
    driver: local
```

---

## Alembic Setup

### Installation

```bash
cd AgriGuard/backend
pip install alembic psycopg2-binary
alembic init alembic
```

### Configuration (`alembic/env.py`)

```python
from AgriGuard.backend.models import Base

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # ... (표준 Alembic 설정)
```

### Generate Migration

```bash
alembic revision --autogenerate -m "initial migration from SQLite"
alembic upgrade head
```

---

## Data Migration Script

### `scripts/migrate_sqlite_to_postgres.py`

```python
import sqlite3
import psycopg2
from sqlalchemy import create_engine

def migrate_data(sqlite_url: str, postgres_url: str):
    """SQLite 데이터를 PostgreSQL로 마이그레이션"""
    # 1. SQLite에서 데이터 읽기
    sqlite_conn = sqlite3.connect(sqlite_url)

    # 2. PostgreSQL에 데이터 쓰기
    pg_engine = create_engine(postgres_url)

    # 3. 테이블별 데이터 마이그레이션
    for table in ['users', 'products', 'transactions']:
        # ... 마이그레이션 로직
        pass

if __name__ == "__main__":
    migrate_data(
        "sqlite:///./agriguard.db",
        "postgresql://agriguard:password@localhost:5432/agriguard"
    )
```

---

## Testing

### 병렬 테스트

```bash
# SQLite 환경
pytest AgriGuard/tests/ --database=sqlite

# PostgreSQL 환경
pytest AgriGuard/tests/ --database=postgresql

# 동시성 테스트
pytest AgriGuard/tests/test_concurrency.py -n 10
```

### 성능 벤치마크

```bash
python scripts/benchmark_database.py \
  --sqlite agriguard.db \
  --postgres postgresql://localhost/agriguard \
  --output docs/db_migration_benchmark.md
```

**예상 결과**:
- 읽기 성능: SQLite와 비슷 (로컬 환경)
- 쓰기 성능: PostgreSQL이 10-50% 느릴 수 있음 (네트워크 오버헤드)
- 동시 쓰기: PostgreSQL이 100배 이상 우수

---

## Rollback Plan

1. **환경 변수 복원**
   ```bash
   export DATABASE_URL=sqlite:///./agriguard.db
   ```

2. **애플리케이션 재시작**
   ```bash
   docker compose restart agriguard
   ```

3. **데이터 무결성 확인**
   ```bash
   sqlite3 agriguard.db "SELECT COUNT(*) FROM transactions;"
   ```

---

## Acceptance Criteria

- ✅ PostgreSQL 환경에서 모든 API 테스트 통과
- ✅ 동시 쓰기 테스트 (10+ concurrent writes) 성공
- ✅ 데이터 마이그레이션 스크립트 실행 후 데이터 무결성 확인
- ✅ 롤백 테스트 성공
- ✅ 성능 벤치마크 리포트 작성 (`docs/db_migration_benchmark.md`)
- ✅ CLAUDE.md 업데이트 (SQLite → PostgreSQL 반영)

---

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
- `docs/POSTGRESQL_MIGRATION_PLAN.md`

---

**Estimated Time**: 3-5일
**Blockers**: None
**Next Steps**: Issue #10 (Docker Compose Multi-Service Setup)
