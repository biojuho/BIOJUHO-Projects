# Dashboard Pre-Push Stage Markers

- Date: 2026-06-05
- Scope: pre-push operator visibility for dashboard UI, production build, and bundle budget guards
- Baseline: dashboard UI/build/bundle commands were wired into the pre-push hook, but the push transcript made the production build and bundle-budget stages hard to distinguish from the surrounding smoke output.
- Variant: add explicit stage markers before each dashboard-specific guard.
- Primary KPI: a push transcript now shows when dashboard UI tests, production build, and bundle budget checks begin.
- Guardrails: commands, failure hints, Python smoke bundle, credential checks, MCP runtime probes, workflow gates, completion audit, and objective coverage remain unchanged.

## Adopted Variant

Adopted. `ops/hooks/pre-push` now emits:

- `==> Running dashboard UI tests...`
- `==> Running dashboard production build...`
- `==> Running dashboard bundle budget check...`

## Changed Paths

- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`

## Verification

- `python -m pytest tests\test_pre_push_hook.py -q` -> `6 passed`
- `python ops\hooks\install_hooks.py --check` -> hook current

## Remaining Boundary

This strengthens pre-push evidence readability. It does not complete credential-gated Canva OAuth/OpenAPI execution, GitHub high-volume live refresh with a token, Telegram delivery, OTLP collector shipping, or hosted runtime/tracing operator decisions.

global_objective_complete=false
