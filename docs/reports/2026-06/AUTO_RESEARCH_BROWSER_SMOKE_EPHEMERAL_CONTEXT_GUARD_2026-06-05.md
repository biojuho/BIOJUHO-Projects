# Browser Smoke Ephemeral Context Guard

Generated at: `2026-06-05T11:05:00+09:00`

## Source Signal

- Repository: `microsoft/playwright-mcp`
- Commit: `6dc3470`
- Subject: `docs: clarify persistent profile single-instance limitation (#1601)`
- Source URL: https://github.com/microsoft/playwright-mcp/commit/6dc3470
- Local interpretation: browser automation that reuses a persistent profile can conflict when multiple agents or smoke runs overlap. Local browser smoke should make its isolated context policy explicit and machine-readable.

## A/B Contract

- Variant A: Continue relying on `browser.new_page()` without report-level isolation evidence.
- Variant B: Create a fresh browser context explicitly with `browser.new_context()`, close it in `finally`, and write the isolation policy into JSON/Markdown smoke reports.
- Adopted: Variant B.
- Reason: The script already launches a short-lived headless browser, but the explicit context path and report metadata make the no-persistent-profile contract auditable before parallel browser-smoke usage expands.

## Local Changes

- `ops/scripts/dev_server_browser_smoke.py`
  - Adds `browser_isolation_policy()` with `mode=ephemeral_context`, `persistent_profile=false`, and no `user_data_dir`.
  - Runs routes through `browser.new_context().new_page()` and closes the context before closing the browser.
  - Emits browser isolation fields in JSON and Markdown reports.
- `tests/test_dev_server_browser_smoke.py`
  - Proves validate-only reports include the isolation policy.
  - Proves the runtime path uses `browser.new_context()` rather than `browser.new_page()`.

## Verification

- `python -m pytest tests\test_dev_server_browser_smoke.py -q`
  - `9 passed`
- `python ops\scripts\dev_server_control.py start --target canva-widget-preview --wait-ready --wait-timeout 60 --poll-interval 2 --timeout 60`
  - ready: `canva-widget-preview`
- `python ops\scripts\dev_server_browser_smoke.py --target canva-widget-preview --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_EPHEMERAL_CONTEXT_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_EPHEMERAL_CONTEXT_2026-06-05.md`
  - pass: `1/1` route, failed=`0`
  - `browser_isolation.mode=ephemeral_context`
  - `browser_isolation.persistent_profile=false`
- `python ops\scripts\dev_server_control.py stop --target canva-widget-preview --timeout 20`
  - stopped
- `python ops\scripts\dev_server_status.py --target canva-widget-preview --format table`
  - final state: `UNREADY`
- `python -m pytest tests\test_dev_server_browser_smoke.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q`
  - `28 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid `57` criteria
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `7` requirements

## Boundaries

- This does not claim persistent-profile support; it intentionally avoids persistent profiles for repo-local smoke checks.
- `global_objective_complete=false`.
