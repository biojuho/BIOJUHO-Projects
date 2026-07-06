# AutoResearch Loop: AgriGuard Dashboard and Supply Child Report Contract

- Date: 2026-07-07 KST
- Scope: AgriGuard dashboard-auth and supply-chain child browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/dashboard_auth_browser_smoke.py`
  - `apps/AgriGuard/scripts/supply_chain_browser_smoke.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_DASHBOARD_SUPPLY_CHILD_REPORT_CONTRACT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DASHBOARD_SUPPLY_CHILD_REPORT_CONTRACT_2026-07-07.md`

## Objective

After normalizing click-nav and QR child evidence, the aggregate suite still had two old-style child reports: dashboard-auth recovery and supply-chain. Both passed real browser checks, but standalone JSON consumers had to infer status from `ok`, `passed`, and `total` rather than reading `status`, `failed`, and a compact `summary`.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: every child browser artifact should be directly consumable as standalone evidence, even when normally run under an aggregate parent.

## A/B Hypothesis

- Baseline: dashboard-auth and supply-chain child JSON reports passed live checks but lacked normalized `status`, `failed`, `summary`, and screenshot path aliases.
- Variant: add child report enrichment helpers that preserve existing keys and add normalized evidence metadata.
- Primary KPI: both live child reports expose `status=pass`, `failed=0`, and `summary.failed=0`.
- Guardrails: aggregate suite compatibility remains unchanged, screenshots still validate, and browser pass/fail behavior is unchanged.

## Variant Evidence

Implemented:

- Added `summarize_checks()` and `enrich_launch_evidence_contract()` to dashboard-auth recovery.
- Added `summarize_checks()` and `enrich_launch_evidence_contract()` to supply-chain.
- Updated CLI output to print `pass`/`fail` from report status.
- Added focused tests for both child report contracts.

Live dashboard-auth proof:

```powershell
python apps\AgriGuard\scripts\dashboard_auth_browser_smoke.py --base-url http://127.0.0.1:5174 --json-out var\agriguard-dashboard-auth-child-report-contract-2026-07-07.json --screenshot var\agriguard-dashboard-auth-child-report-contract-2026-07-07.png --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `passed=14`
- `failed=0`
- `total=14`
- `summary.failed=0`
- screenshot exists

Live supply-chain proof:

```powershell
python apps\AgriGuard\scripts\supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --json-out var\agriguard-supply-chain-child-report-contract-2026-07-07.json --screenshot var\agriguard-supply-chain-child-report-contract-2026-07-07.png --timeout-ms 30000
```

Result:

- `status=pass`
- `url=http://127.0.0.1:5174/supply-chain`
- `passed=26`
- `failed=0`
- `total=26`
- `summary.failed=0`
- screenshot exists

Aggregate compatibility proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --json-out var\agriguard-browser-suite-child-report-contracts-2026-07-07.json --output-dir var\agriguard-browser-suite-child-report-contracts-2026-07-07 --timeout-ms 30000
```

Result:

- `evidence_class=ui_click_coverage_only`
- suite steps: passed=5, failed=1, total=6
- child checks: passed=171, failed=1, total=172
- screenshots: passed=18, failed=0, total=18
- failed check remains `qr_path:public_verify_api_responses_no_store`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\dashboard_auth_browser_smoke.py apps\AgriGuard\scripts\supply_chain_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 72 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dashboard-supply-child-report-contract.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-dashboard-supply-child-report-contract.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DASHBOARD_SUPPLY_CHILD_REPORT_CONTRACT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Dashboard-auth and supply-chain child browser artifacts now carry standalone pass/fail metadata while preserving aggregate suite behavior.

## Remaining Blockers

- Admin-routes and product-detail child reports still expose only partial standalone summary metadata.
- Strict launch remains blocked by stale backend/proxy public verify cache headers and the missing outside-repo Firebase Admin service-account file.
