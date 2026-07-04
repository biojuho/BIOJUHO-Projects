# DailyNews Status Gate And Handoff Refresh QC - 2026-07-04

## Scope

- Aligned local AutoResearch status gating with the current DailyNews first-run verifier behavior.
- Refreshed DailyNews canonical MCP launch evidence and DailyNews launch handoff evidence.
- Preserved the existing dirty-worktree boundary: the code/test files changed in this loop are part of a pre-existing untracked ops stack, so this report records the local deltas and verification without sweeping unrelated untracked files into git.

## Local code deltas

- `automation/DailyNews/tests/unit/test_first_run_verifier.py`
  - Replaced stale optional browser-probe launch-gate assertions with contract-driven required-key checks.
  - Kept dashboard artifact/version evidence as launch-gating.
  - Explicitly verifies optional copy/accessibility probes do not fail `_browser_smoke_required_checks_pass`.

- `ops/scripts/auto_research_status.py`
  - Preserves `database_recovery_handoff` in the normalized DailyNews first-run verifier payload.
  - Accepts the verifier's project-only DB recovery next action when `db_live` is `skipped` or `not_configured`, `project_check` is not yet matched, and the action tells the operator to set same-project `SUPABASE_URL` and `DATABASE_URL` then rerun until `project_check=match`.
  - Requires DB recovery browser-copy probes only when `database_recovery_handoff.required` is not false.

- `tests/test_auto_research_status.py`
  - Added regression coverage for the project-only skipped-DB next-action path.
  - Added regression coverage proving missing DB copy probes still fail when DB recovery is required, but are waived when the verifier says the DB recovery handoff is not required.

## Verification

- `python -m pytest tests/unit/test_first_run_verifier.py -q`
  - Result: `30 passed in 2.08s`.

- `python -m pytest tests/test_auto_research_status.py -q`
  - Result: `130 passed in 35.78s`.

- `python ops\scripts\run_workspace_smoke.py --scope mcp --only-check "DailyNews unit tests" --only-check "DailyNews X ops suite" --only-check "DailyNews X ops browser smoke" --only-check "DailyNews X action-log roundtrip smoke" --only-check "DailyNews first-run verifier smoke" --json-out var\workspace-smoke-mcp-dailynews-launch-20260704.json`
  - Result: `passed=5, failed=0, total=5`.
  - Evidence: `var/workspace-smoke-mcp-dailynews-launch-20260704.json`.
  - First-run verifier smoke tail: `DailyNews first-run verifier smoke PASS: 67/67 checks passed`.

- `python ops\scripts\dailynews_launch_handoff_refresh.py --allow-action-required --allow-unexpected-action-required-failures --status-json-out var\auto-research-status-dailynews-handoff-refresh-20260704.json --status-markdown-out docs\reports\2026-07\AUTO_RESEARCH_OPERATOR_STATUS_DAILYNEWS_HANDOFF_REFRESH_2026-07-04.md --secret-scan-json-out var\dailynews-launch-secret-scan-post-write-20260704.json --bundle-json-out var\dailynews-launch-handoff-refresh-current-20260704.json --radar-markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DAILYNEWS_HANDOFF_REFRESH_CURRENT_2026-07-04.md`
  - Result: `status=ok topic=DailyNews live_source=current unexpected_failures=0 radar_auto_refreshed=True secret_scan=valid findings=0 missing=0 scanned=24`.

- `python ops\scripts\auto_research_status.py --json-out var\auto-research-status-current-20260704-after-dailynews-handoff.json --markdown-out var\auto-research-status-current-20260704-after-dailynews-handoff.md --allow-action-required`
  - Result: `auto research status: ok`.
  - DailyNews completion evidence: `dailynews_failed_checks=[]`, `dailynews_launch_evidence_present=true`.
  - Remaining completion blockers: `getdaytrends_strict_readiness_pass`, `getdaytrends_canonical_smoke_pass`.

## Remaining external blocker

- getdaytrends remains blocked by the known external Supabase live DB path:
  - strict readiness: `fail`, `passed=6/9`, failed `cli_smoke_report|scheduler_artifact|live_db_doctor`.
  - canonical smoke: `6/7`, expected external failure `getdaytrends launch readiness gate`.
  - live DB: `diagnostic_error`; recovery packet remains actionable and secret-safe.
