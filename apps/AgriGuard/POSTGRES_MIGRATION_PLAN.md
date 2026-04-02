# AgriGuard PostgreSQL Migration Plan — Week 3

**Date**: 2026-03-25
**Status**: Ready to Execute (pending Docker PostgreSQL confirmation)

---

## Pre-Migration Checklist

- [x] Week 1: Alembic setup, migration-first startup, SQLite baseline stamp (`0001`)
- [x] Week 2: Docker Desktop restored to Linux containers, PostgreSQL validator passed
- [x] Week 3: Data migration + performance benchmark (this document)

## Current Data Volume

| Table | Rows |
|-------|------|
| users | 120 |
| products | 502 |
| tracking_events | 1,503 |
| certificates | 1 |
| sensor_readings | 15,059 |
| **Total** | **17,185** |

File size was suitable for single-batch migration.

---

## Migration Steps

(Completed via interactive automated scripts resolving dependency constraints and truncation properly)

---

## Rollback Plan

If migration fails:
1. PostgreSQL data can be discarded (SQLite is the source of truth)
2. Reset: `docker compose -f AgriGuard/docker-compose.yml down -v`
3. Revert `DATABASE_URL` to SQLite default

---

## Post-Migration

- [x] Update `.env` to use PostgreSQL URL
- [x] Run full test suite against PostgreSQL
- [ ] Monitor for 24h before decommissioning SQLite
- [x] Archive SQLite backup: `agriguard.db.bak`
