# AutoResearch Loop: AgriGuard Browser Suite Evidence Class

- Date: 2026-07-07 KST
- Scope: AgriGuard aggregate browser smoke evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_BROWSER_SUITE_EVIDENCE_CLASS.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_SUITE_EVIDENCE_CLASS_2026-07-07.md`

## Objective

The aggregate browser suite can be run in two materially different ways: strict launch-gated mode, or `--skip-backend-contract-check` mode for UI-click coverage while the backend is known stale. The JSON already exposed the skip flag, but the summary did not classify the evidence mode directly, so skipped-precheck results could be mistaken for ordinary launch evidence.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: runtime evidence should classify whether a gate is strict launch evidence, blocked precheck evidence, or exploratory UI coverage.

## A/B Hypothesis

- Baseline: strict and skipped-precheck suite reports both used `status=fail`, and operators had to infer intent from `skip_backend_contract_check`.
- Variant: add `evidence_class` and `launch_gate` metadata to top-level JSON and stdout summary.
- Primary KPI: strict default run reports `evidence_class=launch_precheck_blocked`; skipped-precheck run reports `evidence_class=ui_click_coverage_only`.
- Guardrails: pass/fail behavior is unchanged, failed checks remain visible, and screenshots/child metadata gates continue to run.

## Variant Evidence

Implemented:

- Added `browser_suite_evidence_contract()` to classify:
  - `command_plan_only`
  - `launch_precheck_blocked`
  - `ui_click_coverage_only`
  - `launch_gated_browser_pass`
  - `launch_gated_browser_fail`
- Added top-level `evidence_class` and `launch_gate`.
- Added summary fields:
  - `evidence_class`
  - `launch_gate_enforced`
  - `operator_action`
- Added focused tests for evidence-mode classification and precheck-failure JSON.

Strict launch-gated proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-suite-evidence-class-strict-2026-07-07.json --output-dir var\agriguard-browser-suite-evidence-class-strict-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `evidence_class=launch_precheck_blocked`
- `launch_gate_enforced=true`
- `failed_precheck_names=[public_verify_cache_headers]`
- `operator_action=resolve failed prechecks before running launch browser smoke`

Skipped-precheck UI-click proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --skip-backend-contract-check --json-out var\agriguard-browser-suite-evidence-class-ui-coverage-2026-07-07.json --output-dir var\agriguard-browser-suite-evidence-class-ui-coverage-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `evidence_class=ui_click_coverage_only`
- `launch_gate_enforced=false`
- suite steps: passed=5, failed=1, total=6
- child checks: passed=171, failed=1, total=172
- screenshots: passed=18, failed=0, total=18
- failed step: `qr_path`
- failed check: `qr_path:public_verify_api_responses_no_store`
- `operator_action=rerun without --skip-backend-contract-check before launch`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 69 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-suite-evidence-class.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-browser-suite-evidence-class.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_SUITE_EVIDENCE_CLASS_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Aggregate browser reports now state whether they are strict launch-gated evidence or UI-click coverage collected with backend contract checks skipped.

## Remaining Blockers

- The strict browser suite is still launch-blocked by `public_verify_cache_headers` on the stale backend/proxy runtime.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
