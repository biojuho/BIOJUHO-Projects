# GetDayTrends (Production Runbook)

Productionized trend pipeline that collects, scores, and drafts social content variants.

Current canonical runtime path:
`automation/getdaytrends/`

---

## What is implemented (current baseline)

- Deterministic CLI and diagnostics:
  - `--version` for CLI metadata
  - `--doctor` for runtime preflight checks
  - `--health-check` as the scheduler/monitor-friendly preflight alias
  - `--stats` for collected-run metrics
  - `--serve` for dashboard server
- Scheduled runner support:
  - `run_scheduled_getdaytrends.ps1` writes per-run summary + per-execution detail logs
  - `logs/scheduler/run_YYYY-MM-DD_HHMMSS.json` records status, exit code, duration, command, and log paths
  - UTF-8 safe output handling and resilient log writes
- Graceful shutdown handling:
  - SIGINT / SIGTERM aware shutdown with shared shutdown state
- User-facing text cleanup in main CLI path
- Machine-readable readiness gate:
  - `scripts/browser_smoke.py` starts the dashboard, clicks the TAP controls, checks desktop/mobile layout, and writes browser evidence
  - `scripts/readiness_check.py` checks CLI smoke, dashboard browser smoke, text hygiene, scheduler artifacts, production docs, and GitHub benchmark evidence
  - `scripts/readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` adds launch-day freshness, clean-runtime, and live PostgreSQL doctor policies for scheduler, CLI smoke, PostgreSQL, and cost DB evidence
  - `logs/readiness/readiness_latest.json` records a versioned readiness summary
- Structured completion plan for remaining hardening in `GETDAYTRENDS_COMPLETION_PLAN.md`

---

## Prerequisites

- Python environment from workspace root `.venv` (recommended)
- Node/OS dependencies are not required for this package
- Environment variables in `.env` (see `.env.example`)
- Dependencies managed by `pyproject.toml` and `uv.lock`

---

## Install

```bash
cd "D:\AI project\automation\getdaytrends"
uv sync --extra dev
cp .env.example .env
```

Edit `.env` and configure:

- `ANTHROPIC_API_KEY`
- any optional provider keys (Notion, Telegram, Slack, SMTP, Google, X)

---

## Core CLI

```bash
python main.py --help
python main.py --version
python main.py --doctor
python main.py --health-check
python main.py --one-shot
python main.py --one-shot --dry-run
python main.py --one-shot --country us --limit 10
python main.py --one-shot --verbose --no-alerts
python main.py --stats
python main.py --serve
```

Supported options (from argparse):

- `--version`
- `--country`
- `--countries`
- `--limit`
- `--one-shot`
- `--dry-run`
- `--verbose`
- `--no-alerts`
- `--doctor`
- `--health-check`
- `--schedule-min`
- `--stats`
- `--serve`

---

## Scheduled run

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -Country "us" -Limit 5
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -DryRun
```

Logs:

- Summary log: `run_scheduled.log`
- Summary fallback log, used if the rolling summary is locked: `logs/scheduler/summary_YYYY-MM-DD_HHMMSS.log`
- Detail logs: `logs/scheduler/run_YYYY-MM-DD_HHMMSS.log`
- Machine-readable artifacts: `logs/scheduler/run_YYYY-MM-DD_HHMMSS.json`

Database fallback:

- `ALLOW_SQLITE_FALLBACK=true` is the default recovery behavior.
- If `DATABASE_URL` is configured but unreachable, startup and pipeline runs fall back to local SQLite and keep the PostgreSQL error masked.

---

## Suggested run policy

- Daily execution:
  - one run window + one highest-confidence output batch
  - avoid multi-window fan-out by default
- Retry policy:
  - prefer one-shot for operator checks before schedule enablement
  - use `--dry-run` for parse/analyze verification
- Failure handling:
 - keep an eye on non-zero exit code from scheduler
 - check the scheduler JSON artifact, detail log, and either the rolling summary or per-run summary fallback for root cause

---

## Health checks

1. `python main.py --doctor`
2. `python main.py --doctor --require-live-db`
3. `python main.py --health-check`
4. `python scripts\smoke_cli.py`
5. `python scripts\browser_smoke.py`
6. `python scripts\check_text_hygiene.py`
7. `python scripts\smoke_cli.py --include-dry-run`
8. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -DryRun`
9. `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db`
10. From workspace root: `python ops\scripts\getdaytrends_launch_secret_scan.py --include-current-artifacts --json-out var\getdaytrends-launch-secret-scan-final-2026-06-07.json`
11. `python main.py --stats`

The smoke script writes a JSON report to `logs/smoke/cli_smoke_latest.json`.
The browser smoke writes a JSON report to `logs/smoke/dashboard_browser_latest.json` and a screenshot to `logs/smoke/dashboard_browser_latest.png`.
The text hygiene script writes a JSON report to `logs/hygiene/text_hygiene_latest.json`.
The readiness script writes a JSON report to `logs/readiness/readiness_latest.json`. Use `--max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` for launch-day checks that should fail stale scheduler or CLI smoke evidence, fail runtime PostgreSQL / cost DB fallback, and include the live PostgreSQL doctor result in the same operator artifact.
The launch secret scan is run from workspace root and should use `--include-current-artifacts` before release handoff so readiness, recovery packets, browser smoke, CLI smoke, workspace smoke, and handoff docs are checked together.
Doctor output uses `[OK]`, `[WARN]`, and `[ERROR]` records with stable check IDs and `fix:` remediation hints. Add `--require-live-db` to run a non-destructive live PostgreSQL `SELECT 1` probe during launch preflight. Database checks also report the effective `DATABASE_URL` source, Supabase pooler URL shape, optional `SUPABASE_URL` project-ref cross-check, DNS reachability, and TCP reachability without printing credentials.

---

## References

- `WORKFLOW.md`: end-to-end runtime flow and module map
- `docs/RUNBOOK_ROLLBACK_FAILOVER.md`: rollback, database failover, and alert failover procedure
- `docs/GITHUB_BENCHMARK_2026-06-04.md`: GitHub comparison and product-hardening decisions
- `GETDAYTRENDS_COMPLETION_PLAN.md`: production completion criteria and backlog
