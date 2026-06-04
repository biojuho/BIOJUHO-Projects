# AutoResearch: Workspace Smoke Metrics

Date: 2026-06-04

## Source-backed prompt

The GitHub modernization radar identified first-class smoke observability as a
recurring gap: existing smoke JSON artifacts were useful for pass/fail evidence,
but not for ranking slow checks or preserving partial progress if the runner
crashed mid-run.

## A/B contract

- Baseline: `run_workspace_smoke.py --json-out` wrote a bare array of result
  objects. Operators could see pass/fail state, but there was no schema version,
  run duration, per-check elapsed time, or partial-progress status.
- Variant: write schema-v1 smoke reports with top-level `duration_seconds`,
  `summary`, `status`, and per-result `elapsed_seconds`. Refresh the JSON file
  after each completed check so partial evidence survives a later crash.
- KPI: report consumers can rank slow checks from machine-readable JSON while
  startup snapshot readers still understand both legacy array reports and the
  new schema-v1 envelope.

## Adopted variant

The schema-v1 writer was adopted.

Implementation:

- `ops/scripts/run_workspace_smoke.py` now records per-check elapsed time, wraps
  JSON output in a schema-v1 envelope, writes via same-directory temp-file
  replacement, and refreshes the report after every completed check.
- `ops/scripts/session_bootstrap.py` and
  `ops/scripts/generate_context_snapshot.py` now summarize both legacy array
  reports and schema-v1 reports.
- `docs/QUALITY_GATE.md` documents the new report fields and partial-report
  behavior.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py ops\scripts\session_bootstrap.py ops\scripts\generate_context_snapshot.py`
  -> PASS
- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py -q -p no:cacheprovider`
  -> `19 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-metrics-2026-06-04.json`
  -> `2/2 PASS`

Live artifact summary:

- `schema_version`: `1`
- `status`: `complete`
- `summary`: `total=2`, `completed=2`, `passed=2`, `failed=0`, `remaining=0`
- `duration_seconds`: `28.028`
- Per-check timings: `cie compile=0.748s`, `cie tests=27.273s`

## Follow-up

Dashboard or CI consumers can now sort smoke evidence by `elapsed_seconds` to
surface slow checks without scraping stdout.
