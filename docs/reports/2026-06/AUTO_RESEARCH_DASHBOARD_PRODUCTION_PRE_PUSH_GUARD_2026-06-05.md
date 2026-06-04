# Dashboard Production Pre-Push Guard

- Date: 2026-06-05
- Scope: pre-push production build and bundle budget guard for the dashboard
- Baseline: the pre-push hook covered Python smoke tests, dashboard API tests, and the dashboard React/Vitest UI suite, but did not run the dashboard production build or bundle budget check before accepting a push.
- Variant: run `npm.cmd --prefix apps/dashboard run build` and `npm.cmd --prefix apps/dashboard run check:bundle` from `ops/hooks/pre-push`.
- Primary KPI: future pushes fail before merge when the dashboard cannot produce a production bundle or exceeds the checked bundle budget.
- Guardrails: keep existing Python smoke bundle, dashboard UI tests, credential handoff checks, MCP runtime probes, workflow gates, completion audit, and objective coverage in place.

## Adopted Variant

Adopted. The pre-push hook now runs the dashboard production build and bundle budget check immediately after the dashboard UI test. The commands use `npm.cmd --prefix` because that form was verified under Git's `sh.exe` and PowerShell.

## Changed Paths

- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`

## Verification

- `npm.cmd --prefix apps/dashboard run build` -> passed; emitted the known Lightning CSS `@extend` warning
- `npm.cmd --prefix apps/dashboard run check:bundle` -> passed; max chunk under `450KB`, entry under `400KB`
- `C:\Program Files\Git\usr\bin\sh.exe -c 'npm.cmd --prefix apps/dashboard run build'` -> passed
- `C:\Program Files\Git\usr\bin\sh.exe -c 'npm.cmd --prefix apps/dashboard run check:bundle'` -> passed
- `python -m pytest tests\test_pre_push_hook.py -q` -> `6 passed`

## Remaining Boundary

This strengthens local regression protection for dashboard production readiness. It does not complete credential-gated Canva OAuth/OpenAPI execution, GitHub high-volume live refresh with a token, Telegram delivery, OTLP collector shipping, or hosted runtime/tracing operator decisions.

global_objective_complete=false
