# AutoResearch Loop: AgriGuard Aggregate Child Declared Status

- Date: 2026-07-07 KST
- Scope: AgriGuard aggregate browser smoke child result metadata
- Owned code paths:
  - `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_CHILD_DECLARED_STATUS.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CHILD_DECLARED_STATUS_2026-07-07.md`

## Objective

All browser child reports now emit normalized standalone status and count metadata. The aggregate suite still discarded those child-declared fields and only exposed recomputed check summaries. Operators reading one aggregate JSON could not directly see each child artifact's own declared `status`, `ok`, `passed`, `failed`, and `total`.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: parent evidence should preserve child-declared verdicts rather than forcing consumers to reopen every child artifact.

## A/B Hypothesis

- Baseline: aggregate result rows exposed `checks_passed`, `checks_failed`, and parent `ok`, but not child-declared status/count fields.
- Variant: add `child_contract_metadata()` and include child-declared `status`, `ok`, `passed`, `failed`, `total`, and summary presence in every result row.
- Primary KPI: aggregate opt-in suite rows show all seven child-declared statuses, including `qr_path|child_status=fail|child_failed=1`.
- Guardrails: aggregate status, failed step names, screenshot validation, and metadata gates remain unchanged.

## Variant Evidence

Implemented:

- Added `child_contract_metadata()`.
- Extended `summarize_child_report()` with:
  - `child_status`
  - `child_ok`
  - `child_passed`
  - `child_failed`
  - `child_total`
  - `child_summary_present`
- Updated the exact child-summary unit test.

Live aggregate opt-in proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --include-unavailable-check --json-out var\agriguard-browser-suite-child-declared-status-2026-07-07.json --output-dir var\agriguard-browser-suite-child-declared-status-2026-07-07 --timeout-ms 30000
```

Result:

- `evidence_class=ui_click_coverage_only`
- suite steps: passed=6, failed=1, total=7
- child checks: passed=186, failed=1, total=187
- screenshots: passed=19, failed=0, total=19
- child rows:
  - `admin_routes`: `child_status=pass`, `child_failed=0`, `child_total=17`
  - `consumer_verify_unavailable`: `child_status=pass`, `child_failed=0`, `child_total=15`
  - `dashboard_auth_recovery`: `child_status=pass`, `child_failed=0`, `child_total=14`
  - `nav`: `child_status=pass`, `child_failed=0`, `child_total=65`
  - `product_detail`: `child_status=pass`, `child_failed=0`, `child_total=23`
  - `qr_path`: `child_status=fail`, `child_failed=1`, `child_total=27`
  - `supply_chain`: `child_status=pass`, `child_failed=0`, `child_total=26`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 75 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-child-declared-status.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-child-declared-status.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CHILD_DECLARED_STATUS_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The aggregate browser report now preserves child-declared verdicts and counts for every child artifact.

## Remaining Blockers

- Strict launch remains blocked by the stale backend/proxy public verify cache-header runtime.
- Source code and tests already enforce public verify no-store headers; the running Docker backend must be safely replaced after the real outside-repo Firebase Admin service-account file is provided.
