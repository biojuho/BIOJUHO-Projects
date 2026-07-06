# AutoResearch Loop: AgriGuard Unavailable Child Report Contract

- Date: 2026-07-07 KST
- Scope: AgriGuard optional consumer-verify-unavailable child browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/consumer_verify_unavailable_browser_smoke.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_UNAVAILABLE_CHILD_REPORT_CONTRACT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_UNAVAILABLE_CHILD_REPORT_CONTRACT_2026-07-07.md`

## Objective

The aggregate browser suite has an explicit opt-in unavailable-service child check. After normalizing the default child reports, this optional child still used the old `ok/passed/total` shape and printed `PASS` without consulting report status. That left the opt-in aggregate path with a weaker standalone child artifact.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: optional browser evidence should follow the same machine-readable report contract as default launch evidence.

## A/B Hypothesis

- Baseline: `consumer_verify_unavailable_browser_smoke.py` lacked `status`, `failed`, `base_url`, `mobile`, `summary`, and `screenshot_path`.
- Variant: enrich the child report before public token redaction and print status plus check counts.
- Primary KPI: live unavailable child JSON reports `status=pass`, `failed=0`, `mobile=true`, and `summary.failed=0`.
- Guardrails: token redaction remains intact, service-worker blocking remains enabled, and aggregate opt-in suite behavior is unchanged.

## Variant Evidence

Implemented:

- Added `summarize_checks()`.
- Added `mobile_viewport()`.
- Added `enrich_launch_evidence_contract()`.
- Updated CLI output to print `pass`/`fail` and check counts.
- Added a focused report-contract test.

Live unavailable child proof:

```powershell
python apps\AgriGuard\scripts\consumer_verify_unavailable_browser_smoke.py --base-url http://127.0.0.1:5174 --intercept-api-failure --json-out var\agriguard-consumer-unavailable-child-report-contract-2026-07-07.json --screenshot var\agriguard-consumer-unavailable-child-report-contract-2026-07-07.png --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `mobile=true`
- `passed=15`
- `failed=0`
- `total=15`
- `summary.failed=0`
- `interceptApiFailure=true`
- screenshot exists

Aggregate opt-in compatibility proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --include-unavailable-check --json-out var\agriguard-browser-suite-include-unavailable-child-report-contract-2026-07-07.json --output-dir var\agriguard-browser-suite-include-unavailable-child-report-contract-2026-07-07 --timeout-ms 30000
```

Result:

- `evidence_class=ui_click_coverage_only`
- suite steps: passed=6, failed=1, total=7
- child checks: passed=186, failed=1, total=187
- screenshots: passed=19, failed=0, total=19
- optional unavailable child: `status=pass`, `passed=15`, `failed=0`, `summary_present=true`
- failed check remains `qr_path:public_verify_api_responses_no_store`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\consumer_verify_unavailable_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 75 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-unavailable-child-report-contract.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-unavailable-child-report-contract.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_UNAVAILABLE_CHILD_REPORT_CONTRACT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The optional unavailable-service browser child now uses the same standalone evidence contract as the default browser suite children.

## Remaining Blockers

- Strict launch remains blocked by the stale backend/proxy public verify cache-header runtime.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
