# AutoResearch Loop: Compose Launch Report

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Give each fail-closed compose launch attempt one machine-readable report that records the exact stage reached, commands planned, commands executed, return codes, and the stop reason.

## Scope and Owned Paths

- `scripts/launch_compose.py`
- `backend/tests/test_launch_compose_script.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Workspace modernization radar refreshed:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-launch-report.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_LAUNCH_REPORT.md`
  - Result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## A/B Hypothesis

Baseline: `scripts/launch_compose.py` prints process output and writes child preflight/browser JSON files, but does not produce one aggregate launch status artifact.

Variant: write `var/agriguard-compose-launch-report.json` by default with:

- schema version
- launch status
- final stage reached
- stop reason
- preflight/compose/browser command plan
- executed stage results and return codes
- child evidence paths

Primary KPI: operator time to identify the failed launch stage from one artifact.

Decision rule: adopt if the report is written on preflight failure, compose failure, compose-only success, browser-smoke success, and browser-smoke failure; dry-run still does not execute launch commands; and canonical AgriGuard smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_compose_script.py -q --basetemp "..\var\tmp\pytest-agriguard-launch-compose-report"
```

Result: `7 passed in 0.50s`.

Current fail-closed launch attempt:

```powershell
python scripts/launch_compose.py --run-browser-smoke --json-out "..\var\agriguard-launch-compose-report-current-preflight.json" --launch-report-json "..\var\agriguard-compose-launch-report-current.json" --browser-smoke-json-out "..\var\agriguard-browser-smoke-suite-compose-launch-report-current.json"
```

Result: expected exit code `1`. `..\var\agriguard-compose-launch-report-current.json` recorded:

- `status`: `fail`
- `stage`: `preflight`
- `stop_reason`: `preflight_failed`
- executed results: `preflight` only

Dry-run plan:

```powershell
python scripts/launch_compose.py --run-browser-smoke --dry-run --launch-report-json "..\var\agriguard-compose-launch-report-dry-run.json" --json-out "..\var\agriguard-launch-compose-report-dry-run-preflight.json"
```

Result: printed the planned preflight, compose, browser-smoke, and launch-report JSON paths without executing launch commands.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-compose-launch-report.json"
```

Result: `passed=5, failed=0, total=5`.

## Adopt Decision

Adopt the aggregate launch report. It follows the AutoResearch source pattern of durable machine-readable status and makes the fail-closed compose launcher easier to operate and audit.

## Remaining Launch Blocker

The report improves launch diagnostics but does not supply operator secrets. Real launch still requires a Firebase Admin service-account JSON file, app-scoped launch secrets, public HTTPS verify URL, and allowed origins.
