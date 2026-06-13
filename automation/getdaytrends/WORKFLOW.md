# GetDayTrends Workflow (v2026-05 production baseline)

This document describes the actual runtime pipeline and required handoff checks for production use.

---

## Runtime entry

1. `run_scheduled_getdaytrends.ps1` (scheduled path)
   - builds runtime context
   - runs `python main.py --one-shot`
   - writes:
     - summary: `run_scheduled.log`
     - summary fallback if the rolling summary is locked: `logs/scheduler/summary_*.log`
     - detail: `logs/scheduler/run_*.log`
     - artifact: `logs/scheduler/run_*.json`
2. `main.py`
   - reads config/env
   - validates via `--doctor` and health states if requested
   - executes `run_pipeline()` (or `--stats`/`--serve` alternatives)

---

## Pipeline phases

### 1) Pre-check

- Parse command options (`--country`, `--countries`, `--limit`, etc.)
- Build `AppConfig`
- Optional doctor checks in `--doctor` mode
- Resolve schedule interval / country list behavior

### 2) Collect

- Gather raw trend sources (scraper layer)
- Normalize results and deduplicate
- Add context data where available

### 3) Score

- Analyzer computes score signals and metadata
- Filter by quality gates and policy settings
- Apply anti-duplicate and category balance guards

### 4) Generate

- Generate short-form variants
- Optionally include quality feedback loops for generated copy
- Persist generated draft metadata per trend/batch

### 5) Persist and notify

- Store trend + tweet batch data
- Optional alert channels (Telegram/Discord/Slack/SMTP) depending flags
- Apply `--no-alerts` when requested

### 6) Post-run

- Emit health/stats metrics if `--stats`
- Scheduler summary log write and process exit code propagation

---

## CLI contract (current)

- `--version`: print build/version and exit
- `--doctor`: environment + dependency health check mode
- `--health-check`: same preflight contract as `--doctor`, intended for monitors
- `--require-live-db`: with `--doctor` or `--health-check`, run a non-destructive live PostgreSQL `SELECT 1` probe
- `--one-shot`: single execution mode (used by scheduler)
- `--dry-run`: collect/analyze validation path
- `--verbose`: detailed logs
- `--no-alerts`: skip outbound alerting
- `--country` and `--countries`: target selection
- `--limit`: limit trends per run
- `--schedule-min`: override loop interval where supported
- `--stats`: print run statistics and exit
- `--serve`: start dashboard server on port `8080`

---

## Operational safeguards

- Encoding:
  - runner and PowerShell script are UTF-8 enabled
  - logs written in UTF-8 to avoid corruption in CI/local history
- Smoke gate:
  - `python scripts\smoke_cli.py` validates `--version`, `--doctor`, `--health-check`, and `--one-shot --stats`
  - `python scripts\smoke_cli.py --include-dry-run` adds the slower `--one-shot --dry-run --limit 1 --no-alerts` path
  - JSON report: `logs/smoke/cli_smoke_latest.json`
- Dashboard browser gate:
  - `python scripts\browser_smoke.py` starts the dashboard server, clicks TAP preset/refresh/dry-run controls, checks console/page errors, verifies visible text hygiene, and records a desktop screenshot plus mobile overflow check
  - JSON report: `logs/smoke/dashboard_browser_latest.json`
  - Screenshot: `logs/smoke/dashboard_browser_latest.png`
- Text hygiene gate:
  - `python scripts\check_text_hygiene.py` checks production docs, GitHub benchmark notes, and the dashboard template for mojibake markers
  - JSON report: `logs/hygiene/text_hygiene_latest.json`
- Readiness gate:
  - `python scripts\readiness_check.py` checks CLI smoke, dashboard browser smoke, text hygiene, scheduler, production docs, and GitHub benchmark evidence
  - `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` fails launch-day readiness when the latest scheduler artifact, CLI smoke report, or dashboard browser smoke report is stale, when smoke evidence only passes through PostgreSQL / cost DB fallback, or when the live DB doctor fails
  - JSON report: `logs/readiness/readiness_latest.json`
  - Recovery packets: `logs/readiness/supabase_recovery_packet_latest.json` and `logs/readiness/provider_auth_recovery_packet_latest.json`
  - Packet verifier: `python scripts\verify_supabase_recovery_packet.py` and `python scripts\verify_provider_auth_recovery_packet.py`; for timestamped packets, pass only `--packet-report` and the verifier reads the embedded readiness report path
- Launch secret scan gate:
  - from workspace root, run `python ops\scripts\getdaytrends_launch_secret_scan.py --include-current-artifacts --json-out var\getdaytrends-launch-secret-scan-final-2026-06-07.json`
  - checks handoff docs plus current readiness, recovery packets, browser smoke, CLI smoke, TAP fixture, workspace smoke, radar, and text hygiene artifacts for value-shaped secrets
- Doctor output:
  - each check prints a stable ID, severity, and remediation hint when action is needed
  - database checks report the effective `DATABASE_URL` source and Supabase pooler shape without printing credentials
  - exit code remains `0` for pass/pass-with-warnings and `2` for blocking errors
  - `python main.py --doctor --require-live-db` is the launch preflight for proving the Supabase/PostgreSQL path before enabling schedule or posting
- Shutdown:
  - graceful SIGINT/SIGTERM handling with shared shutdown flag
  - safe exit path prevents partial runs in most failure modes
- Error handling:
  - one run failing should not block future scheduled invocations
  - scheduler preserves detail logs plus either the rolling summary or a per-run fallback summary for post-mortem
  - scheduler emits a JSON artifact with status, exit code, duration, command, artifact path, log paths, and `summary_fallback_used`
  - one-shot failures raise non-zero process exits instead of being silently logged as success
- Database fallback:
  - `ALLOW_SQLITE_FALLBACK=true` allows local SQLite recovery when PostgreSQL is unavailable
  - fallback warnings mask tenant/user identity and credentials
- Recovery:
  - use `docs/RUNBOOK_ROLLBACK_FAILOVER.md` for rollback, database failover, and alert-channel failover

---

## Verification checklist

Before declaring production-ready after change:

1. `python main.py --version` succeeds
2. `python main.py --doctor` exits with health status
3. `python main.py --doctor --require-live-db` exits with live PostgreSQL status
4. `python main.py --health-check` exits with the same health status
5. `python scripts\smoke_cli.py` writes a passing smoke report
6. `python scripts\browser_smoke.py` writes a passing dashboard browser report and screenshot
7. `python scripts\check_text_hygiene.py` writes a passing text hygiene report
8. `python main.py --one-shot --dry-run` completes with expected output shape
9. `python main.py --stats` returns metrics
10. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1` writes detail and JSON artifact files, plus the rolling summary or per-run fallback summary
11. `docs/RUNBOOK_ROLLBACK_FAILOVER.md` documents rollback, database failover, and alert failover
12. `docs/GITHUB_BENCHMARK_2026-06-04.md` records the GitHub comparison used for product decisions
13. `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` writes a passing readiness report only when scheduler, CLI smoke, browser smoke, PostgreSQL fallback, cost DB fallback, and live DB doctor evidence are clean
14. `python scripts\verify_supabase_recovery_packet.py` and `python scripts\verify_provider_auth_recovery_packet.py` validate the latest recovery packets; timestamped packet artifacts can be checked with `--packet-report` alone
15. From workspace root, `python ops\scripts\getdaytrends_launch_secret_scan.py --include-current-artifacts --json-out var\getdaytrends-launch-secret-scan-final-2026-06-07.json` writes a valid report with no findings or missing paths
16. The readiness report includes `live_db_doctor` diagnostics showing `db.database_url_source`, `db.supabase_url_shape`, and a successful `db.live_postgres` check before production schedule/posting enablement
17. Any doc or dashboard template edits are readable and free of mojibake markers
