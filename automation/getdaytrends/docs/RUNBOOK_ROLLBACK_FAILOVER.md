# GetDayTrends Rollback and Failover Runbook

This runbook covers the fastest safe path when a getdaytrends release, scheduled run, database target, or alert channel fails.

## Scope

- Canonical project path: `automation/getdaytrends`
- Verified Windows runner: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1`
- Primary evidence files:
  - `run_scheduled.log`
  - `logs/scheduler/summary_*.log` if the rolling summary log is locked by another process
  - `logs/scheduler/run_*.log`
  - `logs/scheduler/run_*.json`
  - `logs/smoke/cli_smoke_latest.json`
  - `logs/hygiene/text_hygiene_latest.json`
  - `logs/readiness/readiness_latest.json`
  - Workspace root `var/getdaytrends-launch-secret-scan-final-2026-06-07.json`

## First Response

1. Stop duplicate starts.
   - Check whether a run is active before starting another run.
   - If the CLI reports an existing lock with a live PID, wait for the current run to finish.
2. Preserve evidence.
   - Do not delete the latest scheduler detail log or JSON artifact.
   - Copy the latest error text into the incident note or issue before changing configuration.
3. Run non-destructive checks.
   - `python main.py --health-check`
   - `python scripts\smoke_cli.py`
   - `python scripts\check_text_hygiene.py`

## Rollback

Use rollback when a recent code or configuration change breaks the local health path, scheduler wrapper, or generated artifacts.

1. Disable scheduled execution temporarily.
   - Use Windows Task Scheduler UI, or run `schtasks /Change /TN "GetDayTrends_CurrentUser" /DISABLE` if that task exists.
2. Return to the last known good Git revision or release package.
   - Prefer reverting the specific getdaytrends change set rather than resetting the whole workspace.
   - Preserve unrelated worktree changes outside `automation/getdaytrends`.
3. Restore the last known good `.env` values.
   - Keep provider keys and alert webhook values out of chat and logs.
   - If `DATABASE_URL` is the failure source, unset it to force local SQLite fallback for recovery checks.
4. Validate the rollback.
   - `python main.py --doctor`
   - `python scripts\smoke_cli.py`
   - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea`
5. Re-enable the scheduled task only after the dry-run exits `0` and writes matching detail log plus JSON artifact, with the run boundary in either `run_scheduled.log` or `logs/scheduler/summary_*.log`.

## Database Failover

The package supports local SQLite fallback for dry-run and stats paths. Use this when PostgreSQL or Supabase rejects the configured tenant, blocks network access, or times out.

`ALLOW_SQLITE_FALLBACK=true` is the default runtime recovery setting. If PostgreSQL is unavailable, startup and pipeline DB access should fall back to `DB_PATH` instead of failing the whole run.

1. Confirm the failure.
   - `python main.py --doctor`
   - `python main.py --one-shot --stats`
   - Look for `db.postgres_config` in doctor output and fallback warnings in stats output.
2. Switch to local recovery mode.
   - Temporarily unset `DATABASE_URL` in the shell or `.env`.
   - Keep `db_path` on local disk under `data/`.
3. Validate local operation.
   - `python main.py --one-shot --stats`
   - `python scripts\smoke_cli.py`
4. Restore PostgreSQL only after the provider console confirms the tenant, password, host, and pooler mode.

## Supabase Primary DB Recovery

Use this checklist when strict launch readiness fails on `live_db_doctor` or when CLI smoke evidence shows a PostgreSQL-to-SQLite fallback. Do not paste the raw `DATABASE_URL` into chat, reports, or issue comments.

Current expected healthy shape for the shared Supabase transaction pooler:

- Host: `aws-1-ap-northeast-2.pooler.supabase.com`
- Port: `6543`
- User shape: `postgres.<project_ref>`
- Database: `postgres`
- Optional cross-check: `SUPABASE_URL` should come from the same project, shaped like `https://<project_ref>.supabase.co`

1. Confirm whether the blocker is local reachability or Supabase identity.
   - `python main.py --doctor --require-live-db`
   - If strict readiness generated a timestamped Supabase recovery packet, validate that packet against its embedded readiness report with `python scripts\verify_supabase_recovery_packet.py --packet-report logs\readiness\<readiness_name>_supabase_recovery_packet.json`.
   - If `db.supabase_project_ref_crosscheck` fails, `DATABASE_URL` and `SUPABASE_URL` came from different Supabase projects; copy both values again from the same dashboard project.
   - If `db.supabase_project_ref_crosscheck` warns that `SUPABASE_URL` is missing, manually verify the pooler user project ref in the dashboard Connect panel.
   - If `db.endpoint_dns` fails, fix DNS/network access before changing database credentials.
   - If `db.endpoint_tcp` fails, check firewall/VPN/proxy access to port `6543`.
   - If DNS and TCP pass but `db.live_postgres` fails with masked tenant identity text, fix the Supabase connection data in the Supabase dashboard.
2. Refresh the connection string from Supabase.
   - Open the target project in the Supabase dashboard.
   - Use **Connect** -> **Transaction pooler** / shared pooler connection string.
   - Confirm the project is running, not paused, and the copied user includes the current `postgres.<project_ref>` value.
   - Copy `SUPABASE_URL` from the same project if you want the doctor to cross-check the project ref automatically.
   - Re-enter or rotate the database password if the password is uncertain.
3. Update only the intended env source.
   - The current getdaytrends live doctor reports the effective `DATABASE_URL` source before the live probe.
   - If the source is the workspace root `.env`, update that file or deliberately add a project-local override in `automation/getdaytrends/.env`.
   - Keep `LLM_COSTS_DATABASE_URL` separate from the primary `DATABASE_URL`; cost tracking should not inherit the launch DB unless explicitly intended.
4. Re-run the launch checks after the external fix.
   - `python main.py --doctor --require-live-db`
   - `python scripts\smoke_cli.py --include-dry-run`
   - `python scripts\browser_smoke.py --timeout 45`
   - `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db`
   - From workspace root: `python ops\scripts\getdaytrends_launch_secret_scan.py --include-current-artifacts --json-out var\getdaytrends-launch-secret-scan-final-2026-06-07.json`
   - `python ops\scripts\run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-after-supabase-fix.json`

Reference: https://supabase.com/docs/reference/postgres/connection-strings

## Provider Credential Recovery Packet Check

When strict readiness emits `provider_auth_recovery_packet_latest.json` or a timestamped provider packet, verify the packet before using copied remediation commands:

- Latest packet: `python scripts\verify_provider_auth_recovery_packet.py`
- Timestamped packet: `python scripts\verify_provider_auth_recovery_packet.py --packet-report logs\readiness\<readiness_name>_provider_auth_recovery_packet.json`

The verifier reads the embedded readiness report path when `--readiness-report` is omitted, so timestamped packets can be checked from the packet path alone.

## Alert Failover

Alerting is optional but recommended for unattended runs.

1. If one alert provider fails, keep the pipeline running with another channel.
   - Preferred order: Telegram, Discord, Slack, SMTP.
2. Run `python main.py --doctor` and check `alerts.channels`.
3. If all alert channels are unavailable, run with manual monitoring:
   - Check `run_scheduled.log` after each scheduled window.
   - If `run_scheduled.log` is locked, check the latest `logs/scheduler/summary_*.log`.
   - Check the latest `logs/scheduler/run_*.json` for `status` and `exit_code`.
4. Re-enable alerting only after sending a small test message through the provider-specific configuration.

## Release Gate

Before declaring recovery complete, all of these must pass:

1. `python main.py --version`
2. `python main.py --doctor`
3. `python main.py --doctor --require-live-db`
4. `python main.py --health-check`
5. `python scripts\smoke_cli.py`
6. `python scripts\browser_smoke.py --timeout 45`
7. `python scripts\check_text_hygiene.py`
8. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea`
9. `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db`
10. `python scripts\verify_supabase_recovery_packet.py` and `python scripts\verify_provider_auth_recovery_packet.py`
11. From workspace root: `python ops\scripts\getdaytrends_launch_secret_scan.py --include-current-artifacts --json-out var\getdaytrends-launch-secret-scan-final-2026-06-07.json`

Record the result in `QC_LOG.md` with the exact commands, exit codes, latest artifact paths, and residual risks.
