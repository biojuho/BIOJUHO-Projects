# AutoResearch Loop: Compose Launch Child Summary

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the aggregate compose launch report directly actionable by embedding the relevant child preflight and browser-smoke summaries instead of only linking to child JSON files.

## Scope and Owned Paths

- `scripts/launch_compose.py`
- `backend/tests/test_launch_compose_script.py`

## A/B Hypothesis

Baseline: `var/agriguard-compose-launch-report.json` records the stage and child evidence paths, but operators still need to open the preflight or browser-smoke JSON to see missing launch values or stale-backend details.

Variant: embed child summaries:

- Preflight: `status`, `errors`, and `warnings`.
- Browser smoke: `status`, `summary`, and `prechecks`.
- Missing or malformed child files remain represented as `found=false` instead of crashing the launcher.

Primary KPI: one-file diagnosability for launch failures.

Decision rule: adopt if focused tests cover found/missing child reports, the current fail-closed launch report embeds the missing operator values, and canonical AgriGuard smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_compose_script.py -q --basetemp "..\var\tmp\pytest-agriguard-launch-compose-child-report"
```

Result: `9 passed in 0.58s`.

Current fail-closed launch attempt:

```powershell
python scripts/launch_compose.py --run-browser-smoke --json-out "..\var\agriguard-launch-compose-child-report-current-preflight.json" --launch-report-json "..\var\agriguard-compose-launch-child-report-current.json" --browser-smoke-json-out "..\var\agriguard-browser-smoke-suite-compose-child-report-current.json"
```

Result: expected exit code `1`. The aggregate report recorded:

- `status`: `fail`
- `stage`: `preflight`
- `stop_reason`: `preflight_failed`
- `child_reports.preflight.status`: `fail`
- `child_reports.preflight.errors`: missing `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, `AGRIGUARD_SECRET_KEY`, `AGRIGUARD_QR_TOKEN_PEPPER`, `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and `AGRIGUARD_ALLOWED_ORIGINS`.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-compose-launch-child-report.json"
```

Result: `passed=5, failed=0, total=5`.

## Adopt Decision

Adopt the embedded child summaries. This keeps the launcher aligned with the AutoResearch pattern of durable, machine-readable status while making failed launch attempts easier to inspect from one JSON file.

## Remaining Launch Blocker

The report now identifies the launch blockers in one place, but the values still need to be supplied by the operator before a real compose/browser launch can pass.
