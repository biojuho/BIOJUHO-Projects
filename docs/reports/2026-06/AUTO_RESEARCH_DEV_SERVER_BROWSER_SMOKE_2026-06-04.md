# AutoResearch Dev-Server Browser Smoke - 2026-06-04

## Objective

Adopt the Playwright MCP radar pattern into a local deterministic tool: a
manifest-backed browser smoke runner for dev-server frontends.

## A/B Contract

- Baseline: DeSci had a project-local browser smoke script, and dashboard,
  AgriGuard, and Canva browser evidence lived mainly in per-cycle reports.
- Variant: add `ops/references/dev_server_browser_checks.json` and
  `ops/scripts/dev_server_browser_smoke.py` so browser route checks are
  declared once and can be run by target.
- Primary KPI: the new runner validates all configured frontend route checks
  and passes a live managed DeSci browser run.
- Guardrails: dev-server status/control tests stay green, completion audit stays
  valid, and the pre-push gate includes the new browser-smoke tests.

## Verification

- `python -m py_compile ops\scripts\dev_server_browser_smoke.py tests\test_dev_server_browser_smoke.py`
  - Result: pass.
- `python -m pytest tests\test_dev_server_browser_smoke.py`
  - Result: `4 passed`.
- `python ops\scripts\dev_server_browser_smoke.py --validate-only --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_MANIFEST_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_MANIFEST_2026-06-04.md`
  - Result: valid, `10` configured routes.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-generic-browser-start-2026-06-04.json start --target desci-frontend --wait-ready --wait-timeout 150 --poll-interval 2 --timeout 5`
  - Result: ready, DeSci frontend pid `20368`, attempts `3`.
- `python ops\scripts\dev_server_browser_smoke.py --target desci-frontend --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DESCI_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DESCI_2026-06-04.md`
  - Result: pass, `5/5` routes, no failures.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-generic-browser-stop-2026-06-04.json stop --target desci-frontend --include-dependencies --timeout 10`
  - Result: stopped.
- `python -m pytest tests\test_dev_server_browser_smoke.py tests\test_dev_server_status.py tests\test_dev_server_control.py tests\test_github_modernization_radar.py tests\test_pre_push_hook.py tests\test_autoresearch_completion_audit.py`
  - Result: `34 passed`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-browser-smoke-2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_BROWSER_SMOKE_2026-06-04.md`
  - Result: valid, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.
- `git push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - Result: installed pre-push hook passed `47` tests, MCP subprocess smoke, and
    completion audit; Git reported `Everything up-to-date`.

## Decision

Adopted. The workspace now has a manifest-backed browser smoke runner aligned
with the Playwright MCP/browser-automation radar source while keeping execution
local, deterministic, and target-scoped.
