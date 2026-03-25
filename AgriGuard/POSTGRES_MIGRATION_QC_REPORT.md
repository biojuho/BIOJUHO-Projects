# AgriGuard PostgreSQL Migration QC Report

**Date:** 2026-03-25
**Status:** PASSED (5/5 checks)
**Environment:** PostgreSQL 16 via `AgriGuard/docker-compose.yml`
**SQLite Source:** `AgriGuard/backend/agriguard.db`
**PostgreSQL Target:** `postgresql://agriguard:***@localhost:5432/agriguard`

---

## Summary

AgriGuard is running against PostgreSQL and the latest quality-control pass succeeded from the repository root. Static tables match exactly between SQLite and PostgreSQL. The only expected variance is `sensor_readings`, which continues to change while the system is live and is therefore validated with a tolerance threshold.

This report should be read together with:
- `AgriGuard/BENCHMARK_RESULTS.md`
- `AgriGuard/backend/scripts/qc_postgres_migration.py`
- `TASKS.md`
- `HANDOFF.md`

---

## Latest QC Snapshot

The latest QC run completed with `5/5` checks passing:

1. Row count comparison
2. Boolean type verification
3. Foreign key integrity
4. Sample data integrity
5. Schema structure validation

### Row Count Outcome

- `users`, `products`, `tracking_events`, and `certificates` matched exactly.
- `sensor_readings` remained within the configured drift tolerance of `500` rows.
- The drift is expected while live sensor ingestion continues.

### Foreign Key Outcome

- Two `products -> users` references point to development/test owners:
  - `demo-user`
  - `farmer-001`
- This is acceptable for the current development environment and does not block cutover monitoring.

### Type Conversion Outcome

- PostgreSQL boolean columns in `products` were validated successfully.
- No invalid boolean rows were detected.

---

## Benchmark Notes

The latest benchmark snapshot is stored in `AgriGuard/BENCHMARK_RESULTS.md`.

Current interpretation:
- SQLite is still faster for several small local queries because of lower connection overhead.
- PostgreSQL is the correct operational target because it supports the intended deployment model, connection pooling, and larger-scale workloads.
- Benchmark results should be treated as a point-in-time snapshot because live `sensor_readings` volume changes continuously.

---

## Operational Guidance

### Safe to do now

- Keep PostgreSQL as the active backend.
- Re-run QC after the monitoring window:

```powershell
$env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
python AgriGuard/backend/scripts/qc_postgres_migration.py
```

### Do not do blindly

- Do not rerun the live migration into the existing PostgreSQL target unless you intentionally want to overwrite data.
- `migrate_sqlite_to_postgres.py` now blocks live migration into a populated target unless `--truncate` is provided.

### If a controlled resync is required

1. Pause or isolate live writes if possible.
2. Confirm that overwriting PostgreSQL is intended.
3. Run:

```powershell
$env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
python AgriGuard/backend/scripts/migrate_sqlite_to_postgres.py --truncate
python AgriGuard/backend/scripts/qc_postgres_migration.py
```

---

## Remaining Follow-up

- Continue cutover monitoring until the team is comfortable archiving the SQLite file.
- Archive `AgriGuard/backend/agriguard.db` to `agriguard.db.bak` after the monitoring window.
- Clean up test/demo user references before production deployment.
- Revisit PostgreSQL performance tuning only after the operational cutover is fully settled.

---

## Conclusion

**Assessment:** PostgreSQL cutover validation is in good shape, with monitoring still recommended because live `sensor_readings` drift is normal in the current environment.
