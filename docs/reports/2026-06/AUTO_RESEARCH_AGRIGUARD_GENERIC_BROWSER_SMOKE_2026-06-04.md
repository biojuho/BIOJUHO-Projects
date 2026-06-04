# AutoResearch AgriGuard Generic Browser Smoke - 2026-06-04

## Objective

Run the manifest-backed browser smoke runner against AgriGuard after the
dashboard and DeSci generic browser proofs.

## A/B Contract

- Baseline: AgriGuard had earlier app-click reports, but the new generic
  `dev_server_browser_smoke.py` runner had not yet committed AgriGuard target
  evidence.
- Variant: run `dev_server_browser_smoke.py --target agriguard-frontend` against
  the live local AgriGuard stack.
- Primary KPI: all configured AgriGuard routes pass with no console/page/request
  failures.
- Guardrails: do not stop services that were already running before this cycle;
  focused browser/status tests and completion audit remain green.

## Verification

- `python ops\scripts\dev_server_browser_smoke.py --validate-only --target agriguard-frontend --json-out var\dev-server-browser-smoke-agriguard-validate-2026-06-04.json`
  - Result: valid, `3` configured routes.
- `python ops\scripts\dev_server_status.py --target agriguard-api --target agriguard-frontend --format table`
  - Result before browser smoke: both targets `READY`.
- `python ops\scripts\dev_server_browser_smoke.py --target agriguard-frontend --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_AGRIGUARD_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_AGRIGUARD_2026-06-04.md`
  - Result: pass, `3/3` routes, no failures.
- `python -m pytest tests\test_dev_server_browser_smoke.py tests\test_dev_server_status.py`
  - Result: `16 passed`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-agriguard-browser-smoke-2026-06-04.json`
  - Result: valid, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.

## Decision

Adopted. AgriGuard now has committed generic browser-smoke evidence for home,
registry, and supply-chain routes under the shared manifest-backed runner.
