# AutoResearch Loop - AgriGuard Browser Failure Index

Date: 2026-07-04

## Objective

Make aggregate browser-smoke evidence immediately actionable by surfacing failed
precheck, step, and child-check names in `run_browser_smoke_suite.py` output.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_BROWSER_FAILURE_INDEX.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system`
  - Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: aggregate browser-smoke JSON has pass/fail counts, but operators
  must inspect child JSON files or precheck details to identify the failed item.
- Variant: aggregate JSON adds `failed_step_names`, `failed_check_names`, and
  `failed_precheck_names`, while each child summary includes
  `failed_check_names`.
- Primary KPI: live aggregate browser suite failure reports the failed precheck
  name directly in `summary.failed_precheck_names`.
- Guardrail: existing smoke-script tests and canonical AgriGuard smoke stay
  green.
- Decision: adopted.

## Variant Evidence

- Child report summarization now records failed check names and falls back to
  `check_<n>` for unnamed failed checks.
- Aggregate browser-smoke summary now records:
  - `failed_step_names`
  - `failed_check_names`
  - `failed_precheck_names`
- Precheck short-circuit reports now include the same failure-index fields.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q
```

Result: `26 passed in 28.90s`

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --dry-run --json-out var\agriguard-browser-smoke-suite-failure-index-dry-run.json --output-dir var\agriguard-browser-smoke-suite-failure-index-dry-run --mobile
```

Result: planned 5 steps, `failed_step_names=[]`, `failed_check_names=[]`, `failed_precheck_names=[]`.

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-failure-index.json --output-dir var\agriguard-browser-smoke-suite-failure-index --timeout-ms 30000
```

Result: expected fail-closed precheck stop against the currently running stale
backend:

- `summary.failed_precheck_names=["backend_contract"]`
- missing paths: `/qr-events/kpis`, `/qr-events/kpis/trend`,
  `/qr-tokens/products/{product_id}`, `/sensor-devices`,
  `/sensor-devices/{sensor_id}`
- detail: `backend OpenAPI contract is missing browser-smoke routes; restart/rebuild the backend`

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-failure-index.json
```

Result: `passed=5 failed=0 total=5`

Backend test tail in smoke JSON: `571 passed, 2 warnings in 253.46s (0:04:13)`

## Commit and Push Status

Prepared for explicit staging, commit, and push after this report is written.

## Next Cycle

Refresh or restart the local AgriGuard backend/frontend runtime before the next
live browser pass, then rerun the aggregate suite to separate runtime staleness
from any real browser-path regressions.
