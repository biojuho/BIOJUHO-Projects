# AutoResearch Loop: AgriGuard Click-Nav Report Contract

- Date: 2026-07-07 KST
- Scope: AgriGuard direct app-click browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/nav_browser_smoke.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_CLICK_NAV_REPORT_CONTRACT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CLICK_NAV_REPORT_CONTRACT_2026-07-07.md`

## Objective

The direct click-nav browser smoke already exercised the launch UI with real Playwright clicks, but its standalone JSON report only exposed `ok`, `passed`, and `total` as top-level launch signals. That made the direct app-click evidence weaker than the aggregate browser suite report for operators and automation that expect `status`, `failed`, `base_url`, and a compact summary.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: direct browser/runtime evidence should include machine-readable pass/fail metadata, not just raw child checks.

## A/B Hypothesis

- Baseline: `nav_browser_smoke.py` direct reports passed real desktop and mobile click tests, but lacked normalized top-level `status`, `failed`, and `base_url`.
- Variant: preserve the existing report shape and add normalized launch-evidence fields plus a `summary` block.
- Primary KPI: desktop and mobile click-nav JSON reports expose `status=pass`, `failed=0`, `base_url=http://127.0.0.1:5174`, and `summary.failed=0`.
- Guardrails: the Playwright click path remains unchanged, screenshots are still emitted for every route, and focused/browser/workspace tests remain green.

## Variant Evidence

Implemented:

- Added `summarize_checks()` to `nav_browser_smoke.py`.
- Added top-level fields:
  - `status`
  - `base_url`
  - `failed`
  - `summary`
  - `screenshot_dir`
- Preserved existing compatibility fields:
  - `ok`
  - `passed`
  - `total`
  - `baseUrl`
  - `screenshotDir`
- Added a regression test for failed check naming and summary counts.

Live desktop app-click proof:

```powershell
python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5174 --click-nav --json-out var\agriguard-click-nav-report-contract-desktop-2026-07-07.json --screenshot-dir var\agriguard-click-nav-report-contract-desktop-2026-07-07 --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `passed=65`
- `failed=0`
- `total=65`
- `summary.failed=0`
- `mode=click-nav`
- screenshots written: 7 PNG files

Live mobile app-click proof:

```powershell
python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5174 --click-nav --mobile --json-out var\agriguard-click-nav-report-contract-mobile-2026-07-07.json --screenshot-dir var\agriguard-click-nav-report-contract-mobile-2026-07-07 --timeout-ms 30000
```

Result:

- `status=pass`
- `base_url=http://127.0.0.1:5174`
- `passed=65`
- `failed=0`
- `total=65`
- `summary.failed=0`
- `mode=click-nav`
- `mobile=true`
- screenshots written: 7 PNG files

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\nav_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 68 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-click-nav-report-contract.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-click-nav-report-contract.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CLICK_NAV_REPORT_CONTRACT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The direct click-nav browser smoke now produces standalone launch evidence with normalized pass/fail metadata while keeping the existing child-report contract that the aggregate browser suite already consumes.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
