# AutoResearch Loop: AgriGuard QR Child Report Contract

- Date: 2026-07-07 KST
- Scope: AgriGuard QR path child browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/qr_path_browser_smoke.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_QR_CHILD_REPORT_CONTRACT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_CHILD_REPORT_CONTRACT_2026-07-07.md`

## Objective

The aggregate browser suite correctly identifies the QR path as the only skipped-precheck UI-click failure, but the QR child report itself still lacked normalized standalone evidence fields. It had `ok`, `passed`, `total`, `baseUrl`, and `apiUrl`, but not `status`, `failed`, `base_url`, `api_url`, `mobile`, or a compact summary. Its console output also printed `PASS` even when one child check failed.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: every child browser artifact should be useful as standalone machine-readable evidence, not only through an aggregate parent report.

## A/B Hypothesis

- Baseline: `qr_path_browser_smoke.py` child JSON required consumers to infer failed count from checks and did not expose normalized snake-case URLs or mobile classification.
- Variant: enrich normal and exception reports with `status`, `failed`, `summary`, `base_url`, `api_url`, `mobile`, and `screenshot_dir`.
- Primary KPI: live QR child JSON reports `status=fail`, `failed=1`, and `summary.failed_check_names=[public_verify_api_responses_no_store]`.
- Guardrails: public QR tokens remain redacted, screenshots still validate through the aggregate suite, and existing aggregate failure semantics do not change.

## Variant Evidence

Implemented:

- Added `summarize_checks()`.
- Added `mobile_viewport()`.
- Added `enrich_launch_evidence_contract()` for normal and exception reports.
- Updated CLI output to print `pass` or `fail` based on report status.
- Added a focused regression test for the child report contract.

Live QR child proof:

```powershell
python apps\AgriGuard\scripts\qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-qr-path-child-report-contract-2026-07-07.json --screenshot-dir var\agriguard-qr-path-child-report-contract-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `base_url=http://127.0.0.1:5174`
- `api_url=http://127.0.0.1:8002`
- `mobile=true`
- `passed=26`
- `failed=1`
- `total=27`
- `summary.failed=1`
- `summary.failed_check_names=[public_verify_api_responses_no_store]`
- screenshots written: 3 PNG files

Aggregate compatibility proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --json-out var\agriguard-browser-suite-qr-child-report-contract-2026-07-07.json --output-dir var\agriguard-browser-suite-qr-child-report-contract-2026-07-07 --timeout-ms 30000
```

Result:

- `evidence_class=ui_click_coverage_only`
- suite steps: passed=5, failed=1, total=6
- child checks: passed=171, failed=1, total=172
- screenshots: passed=18, failed=0, total=18
- failed check: `qr_path:public_verify_api_responses_no_store`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\qr_path_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 70 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-child-report-contract.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-qr-child-report-contract.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_CHILD_REPORT_CONTRACT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The QR child browser artifact is now standalone launch evidence with normalized pass/fail metadata while preserving aggregate suite compatibility.

## Remaining Blockers

- The QR child still correctly fails `public_verify_api_responses_no_store` because the current backend/proxy runtime is stale and missing no-store public verify headers.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
