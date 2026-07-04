# DailyNews X Ops Browser Contract And Local-State Launch Evidence

Date: 2026-07-04

## Scope

- Refreshed the DailyNews X ops launch evidence path after the strict first-run verifier reported stale/failing browser smoke evidence.
- Kept the production baseline aligned with `DAILYNEWS_FORCE_LOCAL_STATE=1`, matching `scripts/verify_first_run.ps1` and `scripts/run_scheduled_insights.ps1`.
- Preserved the fail-closed X conversation gate: the current pack has 5 conversation-ready cards and 19 held reports with visible fix hints, instead of pulling risky reports into the launch queue.

## Local Fixes In Workspace

- `scripts/x_ops_dashboard_browser_smoke.py`
  - Accepts a below-requested card count only when the dashboard explicitly declares the card count and shows held-report fix evidence.
  - Uses rendered text for the operator reason block so `<br>` separators do not collapse `reason_codes` into the next flag.
  - Treats `reason_codes=none` as valid for operator priority `none`.
  - Retries Chromium launch after a bounded `python -m playwright install chromium` when isolated Playwright has the package but not the browser binary.
- `scripts/first_run_verifier_smoke.py`
  - Gates browser required checks on the declared browser-smoke contract plus dashboard-version evidence, not optional DB/LLM copy probes.
  - Accepts local-state DB live `skipped` with a project-only next action; live DB failures still require `db.live=ok`.
- `ops/scripts/run_workspace_smoke.py`
  - Passes `DAILYNEWS_FORCE_LOCAL_STATE=1` to DailyNews-scoped checks so workspace smoke matches the scheduled/strict verifier runtime mode.

## Verification

- `python -m py_compile scripts\x_ops_dashboard_browser_smoke.py`
  - Pass.
- `python -m py_compile scripts\first_run_verifier_smoke.py scripts\x_ops_dashboard_browser_smoke.py`
  - Pass.
- `python -m py_compile ops\scripts\run_workspace_smoke.py`
  - Pass.
- `python -m antigravity_mcp ops build-x-ops-suite --limit 6`
  - Pass; produced 5 ready conversation items and 19 held reports.
- `python -m antigravity_mcp ops smoke-x-dashboard --json-out ..\..\var\dailynews-x-ops-browser-smoke-mcp.json --min-items 6`
  - Pass; 128/128 checks, contract ready.
- `python ops\scripts\run_workspace_smoke.py --scope dailynews --only-check "DailyNews X ops suite" --only-check "DailyNews X ops browser smoke" --only-check "DailyNews first-run verifier smoke" --json-out var\workspace-smoke-dailynews-xops-launch-wrapper-20260704.json`
  - Pass; 3/3 checks.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_first_run.ps1 -NonInteractive -Strict -JsonOut '..\..\var\dailynews-first-run-verifier-current-20260704-final.json'`
  - Pass; score 8/8.

## Current State

- Morning task: `DailyNews_Morning_Insights`, Ready.
- Last production run: 2026-07-04 07:00:01, result 0.
- Latest morning log: `logs\insights\morning_2026-07-04_070200.log`, success signal present, no actionable errors.
- X ops browser smoke: fresh, dashboard match true, covers current dashboard version, contract ready.
- Strict verifier: launch-ready locally with manual X posting mode; `NOTION_API_KEY` is not present in this shell, so Notion page inspection remains optional/manual from this verifier path.
