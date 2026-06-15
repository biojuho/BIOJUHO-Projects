# GetDayTrends Completion Plan (Finalized)

Version: 2026-05 (KST scope)
Status: production hardening phase

---

## 1. Completed items

### A. CLI and operator experience

- [x] `--version` argument added in `main.py`
- [x] Existing arguments (`--doctor`, `--stats`, `--serve`, `--dry-run`, `--one-shot`, etc.) confirmed
- [x] `--health-check` monitor alias added for the doctor/preflight contract
- [x] `--require-live-db` added for opt-in live PostgreSQL `SELECT 1` launch preflight
- [x] `scripts/smoke_cli.py` added for a single-command CLI smoke gate
- [x] `--doctor` output includes stable check IDs, severity levels, and remediation hints
- [x] `--doctor --require-live-db` reports the effective `DATABASE_URL` source and Supabase pooler shape without exposing credentials
- [x] ASCII-safe user-facing strings in main CLI path cleaned
- [x] `SIGINT`/`SIGTERM` safe shutdown state restored (`_SHUTDOWN_FLAG`)

### B. Scheduled runner

- [x] `run_scheduled_getdaytrends.ps1` uses UTF-8 streams and env-safe output
- [x] Stable log strategy:
  - summary log file: `run_scheduled.log`
  - summary fallback log file if the rolling summary is locked: `logs/scheduler/summary_YYYY-MM-DD_HHMMSS.log`
  - detail logs: `logs/scheduler/run_YYYY-MM-DD_HHMMSS.log`
- [x] Retry-safe log append behavior in scheduler
- [x] Per-run JSON artifact emitted beside detail logs (`logs/scheduler/run_*.json`) with `artifact_path` and `summary_fallback_used`
- [x] Summary log mixed-encoding recovery added for legacy UTF-16/NUL log content
- [x] Canonical path check and runtime bootstrap kept explicit (`automation/getdaytrends`)

### C. Runtime resilience

- [x] PostgreSQL failure falls back to local SQLite when `ALLOW_SQLITE_FALLBACK=true`
- [x] `--version` bypasses duplicate-run lock checks
- [x] one-shot pipeline failures propagate as non-zero process failures

### D. Documentation readiness

- [x] `README.md` rewritten as readable production runbook
- [x] `WORKFLOW.md` rewritten with clear entry points, phases, and verification list
- [x] `docs/RUNBOOK_ROLLBACK_FAILOVER.md` added for rollback, database failover, and alert failover
- [x] `scripts/check_text_hygiene.py` added for CI-friendly mojibake detection in key docs
- [x] Production docs are UTF-8 readable and covered by the text hygiene gate
- [x] `docs/GITHUB_BENCHMARK_2026-06-04.md` records the GitHub comparison used for the final hardening pass
- [x] `scripts/readiness_check.py` added for one-command production evidence review
- [x] `scripts/readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` added for launch-day scheduler, CLI-smoke freshness, browser-smoke freshness, clean runtime fallback, and live DB doctor policy checks
- [x] Dashboard HTML template cleaned so the visible operator UI no longer ships mojibake text
- [x] `scripts/browser_smoke.py` added for dashboard launch, TAP-control clicks, console/page-error checks, screenshot evidence, and mobile overflow checks
- [x] Text hygiene gate now includes the dashboard template
- [x] Operator dashboard shows exact remediation commands when scheduler or readiness evidence is stale/missing

---

## 2. Production acceptance criteria

All of these must pass before release:

1. `python main.py --version`
2. `python main.py --doctor`
3. `python main.py --doctor --require-live-db`
4. `python main.py --health-check`
5. `python scripts\smoke_cli.py`
6. `python scripts\browser_smoke.py`
7. `python scripts\check_text_hygiene.py`
8. `python main.py --one-shot --dry-run`
9. `python main.py --one-shot --stats`
10. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1`
11. `logs/scheduler/run_*.log` and either `run_scheduled.log` or `logs/scheduler/summary_*.log` contain matching run boundary entries
12. `logs/scheduler/run_*.json` contains status, exit code, duration, command, artifact path, log paths, and `summary_fallback_used`
13. Scheduler exit code is 0 on normal completion, non-zero on failure
14. `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db` writes `logs/readiness/readiness_latest.json` with status `pass`
15. `/api/operator/readiness` and the dashboard Posting blockers panel preserve copyable remediation commands for stale scheduler evidence, missing readiness evidence, runtime fallback evidence, and `live_db_doctor` evidence
16. `live_db_doctor` reports `db.database_url_source`, `db.supabase_url_shape`, `db.supabase_project_ref_crosscheck`, `db.endpoint_dns`, `db.endpoint_tcp`, and `db.live_postgres` without leaking credentials or tenant identity details

Current launch status on 2026-06-16: base readiness (`scripts/readiness_check.py --max-cli-smoke-age-hours 24`) is `8/8 PASS` after refreshing CLI smoke and scheduler evidence — code, tests, docs, scheduler, and browser evidence are all green. The strict launch gate has exactly two remaining failures, both requiring an external/credential action that cannot be completed locally:

1. `live_db_doctor` — Supabase is unreachable. The live doctor confirms the effective `DATABASE_URL` comes from the workspace root `.env`, uses the Supabase transaction pooler on port `6543`, has the `postgres.<project_ref>` user shape, and cross-checks against a same-project `SUPABASE_URL`. DNS and TCP reachability pass, but `db.live_postgres` fails with masked tenant/user text (paused project or rotated pooler credentials), so runtime records one `database.sqlite_fallback` signal. Resume the Supabase project and/or fix the Transaction pooler credentials.
2. `provider_auth_report` (strict `--require-live-llm`) — a leaked/dead provider API key is correctly caught by the live key probe. Rotate the affected key (see security memo) before launch.

After resolving both, rerun the full strict bundle: `python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db --require-live-llm`. Everything else is launch-ready; these two are the only blockers.

**Important context — the product is already running in production.** The
scheduled `getdaytrends.yml` cron (every 4h) is green on its last 8 runs: the
pipeline degrades gracefully around both items above (Supabase down → local
SQLite fallback; leaked Gemini key → Anthropic-first routing), so it keeps
collecting, scoring, generating, and saving drafts. So these two are not
*functional* blockers — the product operates without them. They are an
**optimization gate**: `--require-live-db` enforces a cloud-persistence policy
(durable Postgres rather than ephemeral runner-local SQLite), and the key
rotation restores the Gemini tier. Resuming Supabase upgrades the running
product from degraded-but-working to fully-persistent; it does not switch it on.

---

## 3. 2nd-phase hardening (not yet required for baseline)

All planned 2nd-phase baseline hardening items are complete.

---

## 4. Scope closure

For this turn, getdaytrends is moved from "partially fixed" to "production-ready baseline" with:

- stable runtime contract
- readable docs
- deterministic scheduled behavior
- completion evidence checklist
- GitHub-benchmarked readiness evidence gate

Current code, tests, docs, scheduler, and browser evidence are hardened (base readiness `8/8 PASS` on 2026-06-16). The only remaining release blockers are the two external/credential items described in section 2: live Supabase connectivity (`live_db_doctor` / runtime fallback) and provider key rotation (`provider_auth_report`).

---

## 5. Operator action items (2026-06-16, consolidated)

The code is hardened and the product runs green in production (degraded). These
are the **external/credential/infra actions only the operator can do** — none is
a code defect. Priority order:

1. **Rotate the leaked Google/Gemini key** in 3 places: local `.env`, the GHA
   secret `GOOGLE_API_KEY`, and revoke the old one in the GCP console. Verify
   with `python scripts/check_llm_keys.py`. (Leaked → 403; Anthropic-first
   routing keeps the product working meanwhile.)
2. **Check/rotate the XAI (Grok) key** — `llm_costs.db` shows grok 15/15 calls
   failing with `403 caller does not have permission`. Fix the key or drop Grok
   from routing. Same auth-fail-no-fallback class as the Gemini key.
3. **`npm audit fix`** in `apps/AgriGuard/frontend` and
   `apps/desci-platform/frontend` (form-data HIGH + 2 moderates). This is the
   repo-wide "Quality Gate" / Node-audit blocker — it currently blocks **all**
   PR merges (see `docs/SECURITY_DEPENDENCY_AUDIT_2026-06-16.md`).
4. **Resume Supabase** (paused project → `tenant/user not found`) to upgrade
   from SQLite fallback to durable cloud persistence. Optimization, not a
   function blocker.
5. **Re-issue the Discord alert webhook** (dead — `check_alert_channels.py`
   reports `auth_failed`); Telegram alerts still work meanwhile.
6. **Decide the run cadence** — the `getdaytrends.yml` cron runs every 4h and on
   active days produces 3–5 draft batches (vs the README "1/day" policy). Cost
   impact is negligible ($0.61 worst day vs the $3 budget), so this is a
   cleanliness/policy choice, not urgent.

After (1)+(4), rerun the strict bundle in section 2 to confirm full readiness.
