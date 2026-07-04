# QC Report - GetDayTrends Dashboard Readiness Command and External DB Blocker

Date: 2026-07-04
Scope: `automation/getdaytrends`

## Objective

Refresh getdaytrends runtime evidence after the workspace status reported stale/action-required gates, fix the local regression found by canonical smoke, and preserve the current external blocker classification.

## Findings

- The dashboard readiness refresh command now includes `--require-windows-scheduled-task`.
- Two dashboard tests still expected the older command without that stricter scheduler flag.
- Scheduled and CLI dry-run paths still fail around the live Supabase pooler state:
  - `InternalServerError: (ENOTFOUND) tenant/user *** not found`
  - Runtime fallback is detected as `database.sqlite_fallback`.
  - The scheduled wrapper dry-run exceeded the bounded timeout and wrote a failed scheduler artifact.

## Fix

Updated `tests/test_dashboard.py` so dashboard readiness artifacts and missing-readiness remediation expectations match the stricter command:

```text
python scripts\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db --require-windows-scheduled-task
```

The existing `dashboard.py` command contract already had that stricter scheduler flag.

## Evidence

- `python scripts\smoke_cli.py --include-dry-run --report logs\smoke\cli_smoke_latest.json --python "D:\AI project\.venv\Scripts\python.exe"`
  - Result: fail
  - Summary: `passed=4`, `failed=1`
  - Failure: dry-run timeout at 360s with `database.sqlite_fallback`
- `python scripts\browser_smoke.py --local-db-only --report logs\smoke\dashboard_browser_latest.json --screenshot logs\smoke\dashboard_browser_latest.png --timeout 60`
  - Result: pass, `111/111`
- `python scripts\browser_smoke.py --tap-source-fixture --report logs\smoke\dashboard_browser_tap_source_evidence.json --screenshot logs\smoke\dashboard_browser_tap_source_evidence.png --timeout 60`
  - Result: pass, `117/117`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\run_scheduled_getdaytrends.ps1 -Country korea -Limit 1 -DryRun`
  - Result: bounded timeout, failed scheduler artifact `logs\scheduler\run_2026-07-04_224918.json`
- `python scripts\readiness_check.py --smoke-report logs\smoke\cli_smoke_latest.json --browser-report logs\smoke\dashboard_browser_latest.json --tap-fixture-browser-report logs\smoke\dashboard_browser_tap_source_evidence.json --hygiene-report logs\smoke\text_hygiene_latest.json --scheduler-dir logs\scheduler --report logs\smoke\readiness_latest.json --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db --require-live-llm`
  - Result: fail, `7/10`
  - Passing: dashboard browser, TAP fixture browser, text hygiene, provider auth, live LLM, pooler runtime compatibility, production docs
  - Failing: CLI smoke fallback, scheduler artifact, live DB doctor
- `python -m pytest -c pytest.ini tests/test_dashboard.py::TestDashboardEnhancements::test_operator_readiness_endpoint_summarizes_local_artifacts tests/test_dashboard.py::TestDashboardEnhancements::test_operator_readiness_endpoint_reports_missing_readiness -q`
  - Result: `2 passed`
- `python -m pytest -c pytest.ini tests -q`
  - Result: `1533 passed, 7 skipped`
- `python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-after-dashboard-command-20260704.json`
  - Result: `passed=6`, `failed=1`, `total=7`
  - Remaining failure: expected external `getdaytrends launch readiness gate`

## Decision

Adopt the test fix. The local regression is resolved, and the remaining getdaytrends launch blocker is external Supabase pooler/project credential state plus the resulting runtime fallback and scheduler dry-run failure.
