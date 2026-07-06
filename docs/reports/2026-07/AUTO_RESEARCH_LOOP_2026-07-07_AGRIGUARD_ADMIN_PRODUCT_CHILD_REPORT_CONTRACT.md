# AutoResearch Loop: AgriGuard Admin and Product Child Report Contract

- Date: 2026-07-07 KST
- Scope: AgriGuard admin-routes and product-detail child browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
  - `apps/AgriGuard/scripts/product_detail_browser_smoke.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_ADMIN_PRODUCT_CHILD_REPORT_CONTRACT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ADMIN_PRODUCT_CHILD_REPORT_CONTRACT_2026-07-07.md`

## Objective

Admin-routes and product-detail child reports already exposed `status`, but not the normalized `passed`, `failed`, `total`, `ok`, and `summary` contract now used by the other browser child artifacts. This left the aggregate suite with mixed child report shapes even though all child reports are useful standalone evidence.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: keep child artifacts self-describing and machine-readable even when an aggregate suite consumes them.

## A/B Hypothesis

- Baseline: admin-routes and product-detail child JSON reports had `status`, but omitted count/summary fields and normalized URL aliases.
- Variant: add enrichment helpers that compute `passed`, `failed`, `total`, `ok`, `summary`, `base_url`, `api_url`, and `screenshot_dir` before redaction.
- Primary KPI: aggregate output directory shows all six child reports now expose `status`, `ok`, `passed`, `failed`, `total`, and `summary`.
- Guardrails: public QR token redaction remains in place, screenshots still validate, and aggregate suite pass/fail semantics do not change.

## Variant Evidence

Implemented:

- Added `summarize_checks()` and `enrich_launch_evidence_contract()` to admin-routes.
- Added `summarize_checks()` and `enrich_launch_evidence_contract()` to product-detail.
- Added `baseUrl` and `apiUrl` to admin-routes reports.
- Updated CLI output to include check counts.
- Added focused tests for both child report contracts.

Live admin-routes proof:

```powershell
python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-admin-routes-child-report-contract-2026-07-07.json --screenshot-dir var\agriguard-admin-routes-child-report-contract-2026-07-07 --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `api_url=http://127.0.0.1:8002`
- `passed=17`
- `failed=0`
- `total=17`
- `summary.failed=0`
- screenshots written: 4 PNG files

Live product-detail proof:

```powershell
python apps\AgriGuard\scripts\product_detail_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-product-detail-child-report-contract-2026-07-07.json --screenshot-dir var\agriguard-product-detail-child-report-contract-2026-07-07 --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `api_url=http://127.0.0.1:8002`
- `passed=23`
- `failed=0`
- `total=23`
- `summary.failed=0`
- screenshots written: 2 PNG files

Aggregate compatibility proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --json-out var\agriguard-browser-suite-all-child-report-contracts-2026-07-07.json --output-dir var\agriguard-browser-suite-all-child-report-contracts-2026-07-07 --timeout-ms 30000
```

Result:

- `evidence_class=ui_click_coverage_only`
- suite steps: passed=5, failed=1, total=6
- child checks: passed=171, failed=1, total=172
- screenshots: passed=18, failed=0, total=18
- failed check remains `qr_path:public_verify_api_responses_no_store`
- all six child reports expose `status`, `ok`, `passed`, `failed`, `total`, and `summary`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\admin_routes_browser_smoke.py apps\AgriGuard\scripts\product_detail_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 74 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-admin-product-child-report-contract.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-admin-product-child-report-contract.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ADMIN_PRODUCT_CHILD_REPORT_CONTRACT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The aggregate browser suite now emits a uniform standalone evidence contract across every child report.

## Remaining Blockers

- Strict launch remains blocked by stale backend/proxy public verify cache headers.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
