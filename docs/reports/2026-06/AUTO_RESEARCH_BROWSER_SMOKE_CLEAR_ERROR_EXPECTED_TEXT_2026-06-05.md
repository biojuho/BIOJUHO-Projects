# Browser Smoke Clear-Error Expected Text Guard

Generated at: `2026-06-05T11:13:00+09:00`

## Source Signal

- Repository: `microsoft/playwright-mcp`
- Source commit: `https://github.com/microsoft/playwright-mcp/commit/01adf2d`
- Upstream signal: `fix(extension): throw clear error for tab creation in protocol v1`
- Local mapping: browser-smoke failure evidence should be explicit when a page
  cannot be inspected. If navigation or browser protocol errors prevent body
  text checks, the expected-text evidence must list those strings as missing
  instead of rendering `missing: none`.

## A/B Contract

- Baseline: a browser failure before page inspection could produce
  `expected=0/15` and `missing: none`, even when the route had expected text.
- Variant: mark every unchecked expected text as missing on Playwright timeout
  or browser error while preserving the concrete browser failure message.
- Primary KPI: a regression test raises a Playwright-style clear error and the
  Markdown evidence reports `matched=0/2` with both expected strings listed as
  missing.
- Guardrails: successful routes still record matched text, normal missing text
  still records per-string failures, and manifest validation is unchanged.
- Decision: adopted.

## Changed Files

- `ops/scripts/dev_server_browser_smoke.py`
  - Adds `mark_unchecked_expected_text()` in `run_route()`.
  - Calls it for Playwright timeout and browser error branches.
- `tests/test_dev_server_browser_smoke.py`
  - Adds `test_route_result_marks_expected_text_missing_on_browser_error`.

## Verification

- `python -m pytest tests\test_dev_server_browser_smoke.py -q --tb=line`
  - `9 passed`
- `python -m py_compile ops\scripts\dev_server_browser_smoke.py`
  - passed

## Remaining Boundary

This cycle improves failure evidence for browser automation. It does not change
the dashboard, Canva, AgriGuard, or DeSci user interfaces.

- Pushed proof commit `2efc817` is the active baseline for
  `current_tip_freshness_gate` and `direct_browser_qa_freshness_gate`.
- `global_objective_complete=false`
