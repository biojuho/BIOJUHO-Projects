# AgriGuard SQLite → PostgreSQL Migration Plan

**Created**: 2026-03-22
**Owner**: Backend Team
**Priority**: High
**Target Date**: 2026-04-15 (3 weeks)

---

## Executive Summary

AgriGuard currently uses SQLite (`agriguard.db`) which has concurrency limitations unsuitable for production. This plan outlines migration to PostgreSQL for improved reliability, scalability, and multi-user support.

---

## Current State

| Aspect | Current | Issue |
|--------|---------|-------|
| **Database** | SQLite (`agriguard.db`) | Single-writer limitation |
| **Concurrent Writes** | 1 | Production requires 100+ |
| **ORM** | SQLAlchemy | ✅ DB-agnostic (minimal code changes) |
| **Port** | 8002 | |
| **Data Size** | Unknown | Need assessment |

---

## Migration Strategy

### Phase 1: Preparation (Week 1)

**Tasks**:
- [ ] Install Alembic migration tool
- [ ] Generate initial migration from current schema
- [ ] Set up PostgreSQL Docker container
- [ ] Create `.env.example` with PostgreSQL URL
- [ ] Document current data volume

**Deliverables**:
```bash
# Install Alembic
pip install alembic psycopg2-binary

# Initialize Alembic
cd AgriGuard/backend
alembic init alembic

# Generate initial migration
alembic revision --autogenerate -m "initial schema"
```

### Phase 2: Parallel Testing (Week 2)

**Tasks**:
- [ ] Run PostgreSQL locally via Docker Compose
- [ ] Apply migrations to PostgreSQL
- [ ] Run all tests against PostgreSQL
- [ ] Performance benchmark (SQLite vs PostgreSQL)
- [ ] Fix any compatibility issues

**Docker Compose**:
```yaml
services:
  agriguard-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: agriguard
      POSTGRES_PASSWORD: ${AGRIGUARD_DB_PASSWORD}
      POSTGRES_DB: agriguard
    ports:
      - "5432:5432"
    volumes:
      - agriguard-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "agriguard"]
      interval: 5s
      timeout: 3s
      retries: 5
```

### Phase 3: Data Migration (Week 3)

**Tasks**:
- [ ] Create data export script (SQLite → SQL dump)
- [ ] Test migration on staging environment
- [ ] Validate data integrity (row counts, checksums)
- [ ] Create rollback script
- [ ] Document migration procedure

**Migration Script**:
```python
# scripts/migrate_agriguard_db.py
import sqlite3
import psycopg2
from sqlalchemy import create_engine

def migrate_data():
    # Connect to both DBs
    sqlite_conn = sqlite3.connect('agriguard.db')
    pg_engine = create_engine(os.getenv('DATABASE_URL'))
    
    # Export tables
    tables = ['users', 'crops', 'transactions', 'supply_chain']
    
    for table in tables:
        print(f"Migrating {table}...")
        df = pd.read_sql(f"SELECT * FROM {table}", sqlite_conn)
        df.to_sql(table, pg_engine, if_exists='append', index=False)
        print(f"✅ {len(df)} rows migrated")
    
    sqlite_conn.close()
```

---

## Environment Variables

### Before (SQLite)
```env
DATABASE_URL=sqlite:///./agriguard.db
```

### After (PostgreSQL)
```env
DATABASE_URL=postgresql://agriguard:${AGRIGUARD_DB_PASSWORD}@localhost:5432/agriguard
# or for Docker internal network:
DATABASE_URL=postgresql://agriguard:${AGRIGUARD_DB_PASSWORD}@agriguard-postgres:5432/agriguard
```

---

## Code Changes

### Minimal SQLAlchemy Changes

```python
# Before (no changes needed, SQLAlchemy is DB-agnostic)
from sqlalchemy import create_engine
engine = create_engine(settings.database_url)

# After (same code, just change DATABASE_URL env var)
from sqlalchemy import create_engine
engine = create_engine(settings.database_url)
```

### Connection Pooling (New)

```python
# AgriGuard/backend/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)
```

---

## Testing Checklist

### Unit Tests
- [ ] All existing tests pass with PostgreSQL
- [ ] Transaction rollback tests
- [ ] Concurrent write tests (10+ parallel inserts)

### Integration Tests
- [ ] FastAPI endpoints with PostgreSQL
- [ ] Web3 integration (blockchain transactions → DB)
- [ ] API response times < 500ms (p95)

### Performance Benchmarks

| Operation | SQLite | PostgreSQL | Target |
|-----------|--------|------------|--------|
| Insert (single) | ? ms | ? ms | < 10ms |
| Insert (batch 100) | ? ms | ? ms | < 100ms |
| Query (simple) | ? ms | ? ms | < 50ms |
| Query (join) | ? ms | ? ms | < 200ms |
| Concurrent writes (10) | ❌ Fails | ✅ Pass | 100+ |

---

## Rollback Plan

If migration fails, revert with these steps:

1. **Immediate**: Change `DATABASE_URL` back to SQLite
2. **Restart**: `docker compose restart agriguard`
3. **Verify**: Check API health endpoint
4. **Investigate**: Review logs for root cause
5. **Re-attempt**: Fix issues and retry migration

---

## Production Deployment

### Pre-deployment
- [ ] Backup current `agriguard.db`
- [ ] Schedule maintenance window (2 hours)
- [ ] Notify users of downtime
- [ ] Prepare rollback script

### Deployment Steps
1. Stop AgriGuard service
2. Export SQLite data
3. Start PostgreSQL container
4. Run migrations (`alembic upgrade head`)
5. Import data
6. Validate row counts
7. Start AgriGuard service
8. Smoke test critical endpoints
9. Monitor for 24 hours

### Post-deployment
- [ ] Monitor DB metrics (connections, query times)
- [ ] Set up automated backups (daily)
- [ ] Configure pg_dump cron job
- [ ] Update documentation

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | Critical | Export SQLite before migration, validate checksums |
| Downtime > 2 hours | High | Practice migration in staging, have rollback ready |
| Performance regression | Medium | Benchmark before/after, optimize indexes |
| Connection pool exhaustion | Medium | Configure pool limits, monitor connections |
| Schema incompatibilities | Low | SQLAlchemy abstracts most differences |

---

## Success Metrics

- [ ] Zero data loss (row count validation)
- [ ] Downtime < 2 hours
- [ ] 100+ concurrent writes without errors
- [ ] API p95 latency < 500ms
- [ ] All tests passing
- [ ] No rollback needed

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 (Mar 22-29) | Preparation | Alembic setup, Docker Compose, migrations |
| 2 (Mar 30-Apr 5) | Testing | Parallel testing, benchmarks, fixes |
| 3 (Apr 6-12) | Data Migration | Export script, staging test, validation |
| 4 (Apr 13-15) | Production | Deploy to prod, monitor, celebrate 🎉 |

---

## Team Responsibilities

| Role | Responsibilities |
|------|------------------|
| **Backend Lead** | Oversee migration, code reviews, final approval |
| **DevOps** | Docker setup, production deployment, backups |
| **QA** | Test all scenarios, validate data integrity |
| **Product** | User communication, maintenance window scheduling |

---

## Next Steps

1. [ ] Review this plan with team
2. [ ] Get approval from stakeholders
3. [ ] Create GitHub Issue #4 from checklist
4. [ ] Start Week 1 tasks
5. [ ] Weekly standup on migration progress

---

**Status**: 📋 Planning
**Last Updated**: 2026-03-22
**Next Review**: 2026-03-29
