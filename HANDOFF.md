# Handoff Document

**Last Updated**: 2026-03-25
**Session Status**: Healthy / PostgreSQL Live
**Next Agent**: Claude Code / Gemini / Codex

---

## Latest Follow-Up (2026-03-26)

### Docker Dev Environment
- `docker-compose.dev.yml` was hardened after the AgriGuard cutover work.
- Fixed a Compose interpolation bug in the Mosquitto healthcheck so `$SYS/#` is preserved correctly at runtime.
- Added starter monitoring assets under `monitoring/` so the `monitoring`/`full` profiles now have concrete Prometheus and Grafana config files to mount.
- Fixed `scripts/setup_dev_environment.ps1` to resolve the workspace root correctly from `scripts/` and to fail fast when Docker/Compose commands return non-zero exit codes.

### Validation Status
- Static compose validation passed for the monitoring profile via `docker compose -f docker-compose.dev.yml --profile monitoring config --no-interpolate`.
- `content-intelligence` v2.0 still passes smoke validation (`31 passed`) and `main.py --dry-run`.
- Live Docker status/startup was **not** fully revalidated in this session because the local Docker Desktop Linux engine pipe (`dockerDesktopLinuxEngine`) was unavailable during the script run.
- Root cause of that blocker is now confirmed: Windows `WslService` is configured as `START_TYPE: 4   DISABLED`. `vmcompute` and `com.docker.service` are both stopped, and starting them requires an elevated shell.

### Next Step
1. Open an elevated PowerShell session.
2. Run `Set-Service -Name WslService -StartupType Manual`, then `Start-Service WslService`, `Start-Service vmcompute`, and `Start-Service com.docker.service`.
3. Re-run `powershell -ExecutionPolicy Bypass -File scripts/setup_dev_environment.ps1 -Status`.
4. If healthy, run `powershell -ExecutionPolicy Bypass -File scripts/setup_dev_environment.ps1` or `docker compose -f docker-compose.dev.yml up -d` for full live verification.

---

## Current Status

### AgriGuard PostgreSQL
- Docker PostgreSQL is running and healthy via `AgriGuard/docker-compose.yml`.
- `agriguard-backend` was rebuilt and is healthy on `http://localhost:8002`.
- `AgriGuard/backend/.env` still points to PostgreSQL for local runs.
- The previous drift source is resolved: backend entrypoints now load `AgriGuard/backend/.env` before DB initialization, so fresh local starts no longer fall back to SQLite silently.
- The backend container startup regression is also fixed: `main.py` now discovers the optional `shared` package path safely instead of assuming `parents[2]`.
- PostgreSQL was intentionally resynced from `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` using `migrate_sqlite_to_postgres.py --truncate`.
- `qc_postgres_migration.py` now passes `5/5` against that frozen snapshot.
- After the backend was brought back up, live writes resumed in PostgreSQL. The `sensor_readings` count was `15,062` immediately after restart verification and will continue to grow normally.
- The frozen SQLite resync snapshot has not changed since `2026-03-25 20:05:27 KST`, confirming that ongoing writes are no longer hitting the host SQLite file.

### Key Evidence
- Frozen resync source: `AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555`
- Frozen snapshot QC status: PASS (`5/5`)
- Live service check: `GET /` returned `200` with `{"message":"Welcome to AgriGuard API (DB Connected)","status":"running"}`

---

## What Changed This Session

| File | Change |
|------|--------|
| `AgriGuard/backend/env_loader.py` | Added backend-local `.env` loader for all entrypoints |
| `AgriGuard/backend/database.py` | Load `.env` before resolving `DATABASE_URL`; pin default SQLite path to backend file |
| `AgriGuard/backend/auth.py` | Reused backend-local `.env` loading |
| `AgriGuard/backend/scripts/run_migrations.py` | Load `.env` before Alembic target selection |
| `AgriGuard/backend/alembic/env.py` | Load `.env` before reading migration database URL |
| `AgriGuard/backend/main.py` | Made optional `shared` path discovery safe in Docker and local layouts |
| `AgriGuard/backend/tests/test_env_loading.py` | Added regression coverage for env-file fallback |
| `TASKS.md` | Closed the resync investigation and recorded the completed state |
| `HANDOFF.md` | Replaced the stale resync warning with the current healthy runtime state |

---

## Suggested Follow-Up

1. Keep the frozen SQLite snapshot for audit/reference until you are comfortable deleting it.
2. If local development on port `8002` resumes outside Docker, it should now honor `AgriGuard/backend/.env` automatically.

---

## Active Configuration Notes

- **Python**: 3.13.3 standard, 3.14.2 validated locally
- **Node**: 22.12.0+
- **Git Branch**: `main`
- **Working Directory**: `d:\AI 프로젝트`

---

## Warnings / Gotchas

- There is also a workspace-root `agriguard.db`. Operational scripts should use `AgriGuard/backend/agriguard.db`, not the root-level file.
- The preserved SQLite file is now evidence only. Do not use it as a live source unless you are intentionally repeating a migration exercise.
- The backend container image still does not include the workspace-root `shared/` package; observability remains optional and gracefully disabled in Docker.
