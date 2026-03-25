# Handoff Document

**Last Updated**: 2026-03-25
**Session Status**: Monitoring / Validation
**Next Agent**: Claude Code / Gemini / Codex

---

## Current Status

### AgriGuard PostgreSQL
- Docker PostgreSQL is running and healthy via `AgriGuard/docker-compose.yml`.
- Alembic is applied on PostgreSQL with revision `0001`.
- `AgriGuard/backend/.env` currently points to PostgreSQL.
- The live migration should not be rerun blindly: the target database already contains data, and `migrate_sqlite_to_postgres.py` now refuses that path unless `--truncate` is explicitly provided.
- Latest QC rerun on 2026-03-25 failed the row-count gate (`4/5` overall) because `sensor_readings` drift exceeded the configured tolerance.
- Current snapshot:
  - PostgreSQL `sensor_readings`: `14,102`
  - Archived SQLite snapshot `agriguard.db.archived_20260325`: `14,696`
  - Current backend SQLite file `agriguard.db`: `14,782`
- This means cutover monitoring is not actually closed yet. We need to find out why the backend SQLite file is still growing and whether PostgreSQL needs a controlled backfill.

### Recently Completed (2026-03-25)
- AgriGuard benchmark captured in `AgriGuard/BENCHMARK_RESULTS.md`
- AgriGuard QC script made root-safe and configurable
- GetDayTrends package import compatibility restored
- Workspace package runner and smoke retry flow added

### Previously Completed (2026-03-24)
- AgriGuard PostgreSQL Week 1-2
- GetDayTrends v9.0 Sprint 1-3
- Workspace smoke recovery + NotebookLM auth

---

## Next Immediate Actions

1. Identify what is still writing to `AgriGuard/backend/agriguard.db`.
2. Decide whether PostgreSQL should be backfilled from the archived SQLite snapshot or from the current backend SQLite file.
3. Re-run `python AgriGuard/backend/scripts/qc_postgres_migration.py` after the resync decision.
4. If a full resync is required, stop live writes first and rerun the migration intentionally with `--truncate`.

---

## Key Files Modified This Session

| File | Change |
|------|--------|
| `AgriGuard/backend/scripts/migrate_sqlite_to_postgres.py` | Added populated-target safety check |
| `AgriGuard/backend/scripts/benchmark_postgres.py` | Fixed total-row accounting |
| `AgriGuard/backend/scripts/qc_postgres_migration.py` | Added path-safe defaults and CLI args |
| `AgriGuard/BENCHMARK_RESULTS.md` | Stored latest benchmark snapshot |
| `getdaytrends/__init__.py` | Added root-package import compatibility shim |
| `getdaytrends/collectors/context.py` | Fixed timeout propagation and Jina fallback |
| `scripts/run_workspace_package_script.mjs` | Added package-wide `npm run` walker |
| `scripts/run_workspace_smoke.py` | Added one-time retry for transient Vitest worker startup failures |
| `TASKS.md` | Realigned the task board with the current AgriGuard state |
| `HANDOFF.md` | Replaced stale migration notes with current operational guidance |

---

## Active Configuration Notes

- **Python**: 3.13.3 standard, 3.14.2 validated locally
- **Node**: 22.12.0+
- **Git Branch**: `main`
- **Working Directory**: `d:\AI 프로젝트`

---

## Warnings / Gotchas

- There is also a workspace-root `agriguard.db`. Operational scripts should use `AgriGuard/backend/agriguard.db`, not the root-level file.
- `sensor_readings` currently exceeds the QC drift tolerance, so the earlier "cutover closed" assumption is stale.
- `AgriGuard/backend/agriguard.db` is still changing even though the backend `.env` points to PostgreSQL.
- Do not trust older notes that say AgriGuard is "awaiting Docker PostgreSQL"; that prerequisite is already satisfied.

---

## Suggested Commands

```powershell
$env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
python AgriGuard/backend/scripts/qc_postgres_migration.py
python AgriGuard/backend/scripts/benchmark_postgres.py --pg-url $env:DATABASE_URL --markdown-out AgriGuard/BENCHMARK_RESULTS.md
```

If a controlled resync is needed:

```powershell
$env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
python AgriGuard/backend/scripts/migrate_sqlite_to_postgres.py --truncate
```
