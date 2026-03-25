# AgriGuard PostgreSQL Migration Plan — Week 3

**Date**: 2026-03-25
**Status**: Ready to Execute (pending Docker PostgreSQL confirmation)

---

## Pre-Migration Checklist

- [x] Week 1: Alembic setup, migration-first startup, SQLite baseline stamp (`0001`)
- [x] Week 2: Docker Desktop restored to Linux containers, PostgreSQL validator passed
- [ ] Week 3: Data migration + performance benchmark (this document)

## Current Data Volume

| Table | Rows |
|-------|------|
| users | 120 |
| products | 502 |
| tracking_events | 1,503 |
| certificates | 1 |
| sensor_readings | 0 |
| **Total** | **2,126** |

File size: **749 KB** — small enough for single-batch migration.

---

## Migration Steps

### Step 1: Start PostgreSQL
```powershell
docker compose -f AgriGuard/docker-compose.yml up -d postgres
```

### Step 2: Apply Schema via Alembic
```powershell
cd AgriGuard/backend
$env:DATABASE_URL = "postgresql://agriguard:agriguard@localhost:5432/agriguard"
python scripts/run_migrations.py
```

### Step 3: Dry-Run Migration
```powershell
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

### Step 4: Execute Migration
```powershell
python scripts/migrate_sqlite_to_postgres.py --pg-url $env:DATABASE_URL
```

### Step 5: Verify Row Counts
```sql
SELECT 'users' AS t, COUNT(*) FROM users
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'tracking_events', COUNT(*) FROM tracking_events
UNION ALL SELECT 'certificates', COUNT(*) FROM certificates
UNION ALL SELECT 'sensor_readings', COUNT(*) FROM sensor_readings;
```

### Step 6: Run Benchmark
```powershell
python scripts/benchmark_postgres.py --pg-url $env:DATABASE_URL --markdown-out ../../BENCHMARK_RESULTS.md
```

### Step 7: Smoke Test
```powershell
python -m pytest tests/test_smoke.py -q
```

---

## Rollback Plan

If migration fails:
1. PostgreSQL data can be discarded (SQLite is the source of truth)
2. Reset: `docker compose -f AgriGuard/docker-compose.yml down -v`
3. Revert `DATABASE_URL` to SQLite default

---

## Post-Migration

- [ ] Update `.env` to use PostgreSQL URL
- [ ] Run full test suite against PostgreSQL
- [ ] Monitor for 24h before decommissioning SQLite
- [ ] Archive SQLite backup: `agriguard.db.bak`
