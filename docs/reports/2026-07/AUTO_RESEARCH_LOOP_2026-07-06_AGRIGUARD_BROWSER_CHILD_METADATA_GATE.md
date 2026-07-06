# AutoResearch Loop - AgriGuard Browser Child Metadata Gate - 2026-07-06

## Objective

Make aggregate browser-smoke launch evidence fail closed when a child browser-smoke JSON report is missing `schema_version=1` or a valid ASCII UTC `generated_at` timestamp.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_CHILD_METADATA_GATE_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - Reads child `schema_version` and `generated_at` from every child browser-smoke JSON report.
  - Validates child `generated_at` as ASCII UTC `YYYY-MM-DDTHH:MM:SSZ`.
  - Adds `child_report_metadata_gate_ok` and `child_report_metadata_failures` to step results.
  - Requires child metadata gate success in `child_report_passes_launch_gate`.
  - Adds aggregate summary fields for valid child timestamps and metadata-gate failures.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Updates child report summary expectations for metadata.
  - Adds a regression proving a valid screenshot and passing checks still fail launch gating when child freshness metadata is missing.

## Verification

- Focused browser-smoke aggregate-gate tests:
  - Result: `6 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `63 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-child-metadata-gate.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Dry-Run Evidence

Aggregate browser-smoke command-plan dry run:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --dry-run --include-unavailable-check --output-dir var\agriguard-browser-smoke-suite-child-metadata-gate-dry-run-2026-07-06 --json-out var\agriguard-browser-smoke-suite-child-metadata-gate-dry-run-2026-07-06.json
```

- Result: exit `0`
- Aggregate JSON: `status=pass`, `schema_version=1`, `generated_at=2026-07-06T14:15:59Z`
- Summary metadata fields: `child_report_metadata_failed_steps=[]`, `child_report_metadata_failures=[]`, `child_reports_with_valid_generated_at=0`
- Dry-run coverage: `total=7`, `passed=7`, `include_unavailable_check=true`

## Current Launch State

The aggregate browser-smoke launch gate now treats child report freshness as a first-class contract. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
