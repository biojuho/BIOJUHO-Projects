# AutoResearch DeSci Browser Smoke JSON Evidence - 2026-06-04

## Objective

Turn the DeSci browser smoke from a stdout-only launch check into a durable
machine-readable evidence source, then prove it against the live managed
frontend route path.

## A/B Contract

- Baseline: `apps/desci-platform/scripts/browser_smoke.py` opened the real
  Chromium route path but only printed pass/fail rows, while newer operator
  reports already expected `--json-out` evidence.
- Variant: add a JSON report contract for pass, fail, and infrastructure
  blocked states; document the evidence flag in operator docs.
- Primary KPI: a managed DeSci frontend browser smoke writes a JSON report with
  all planned route checks passing.
- Guardrails: unit tests for report shape, existing dev-server control/status
  tests, live managed start/stop, and affected smoke scope attempt.
- Decision rule: adopt only if the JSON contract is deterministic, the previous
  console output and exit codes are preserved, and live route smoke remains
  green.

## Changed Paths

- `apps/desci-platform/scripts/browser_smoke.py`
- `tests/test_desci_browser_smoke.py`
- `apps/desci-platform/OPERATIONS_RUNBOOK.md`
- `apps/desci-platform/frontend/README.md`
- `docs/reports/2026-06/DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json`

## Verification

- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py tests\test_desci_browser_smoke.py`
  - Result: pass.
- `python -m pytest tests\test_desci_browser_smoke.py`
  - Result: `3 passed`.
- `npm ci` in `apps/desci-platform/frontend`
  - Result: pass; `557 packages` installed locally, `0 vulnerabilities`.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-browser-json-start-ready-2026-06-04.json start --target desci-frontend --wait-ready --wait-timeout 150 --poll-interval 2 --timeout 5`
  - Result: ready, DeSci frontend pid `7740`, attempts `2`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --timeout 30 --json-out docs\reports\2026-06\DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json`
  - Result: pass, `7/7` checks, no failures.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-browser-json-stop-2026-06-04.json stop --target desci-frontend --include-dependencies --timeout 10`
  - Result: stopped.
- `python -m pytest tests\test_desci_browser_smoke.py tests\test_dev_server_control.py tests\test_dev_server_status.py`
  - Result: `24 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-browser-json-2026-06-04.json`
  - Result: outer command timed out after 424 seconds. The partial JSON recorded
    `6/7` completed, `6` passed, `0` failed, with one remaining backend smoke
    check. The orphaned `uv`/pytest child processes from that interrupted smoke
    were stopped after inspection.
- `python ops\scripts\dev_server_status.py --target desci-api --target desci-frontend --format table`
  - Result: both targets stopped/unready after cleanup, as intended.

## Live Evidence

`docs/reports/2026-06/DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json`
contains:

- `schema_version`: `1`
- `tool`: `desci_browser_smoke`
- `status`: `pass`
- `summary`: `total=7`, `passed=7`, `failed=0`, `blocked=0`, `planned=7`
- Protected route checks confirmed final path `/login` for `/dashboard` and
  `/upload`.

## Decision

Adopted. The variant keeps the browser smoke's existing operator output and
exit-code semantics while adding deterministic JSON evidence. The live managed
DeSci route pass proved the new artifact on the real browser path.

## Residual Risk

The full DeSci workspace smoke scope did not finish within this run's command
timeout. It had no failed checks in the partial report, but the backend smoke
check remains unproven in this cycle. The patch itself is limited to the browser
smoke reporting contract, docs, and focused tests.
