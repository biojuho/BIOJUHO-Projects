# Dashboard UI Pre-Push Guard

- Date: 2026-06-05
- Scope: pre-push regression gate for the dashboard React UI suite
- Baseline: dashboard API and browser-manifest guards were in the pre-push gate, but the React/Vitest suite that renders `Credential Operator Checklist`, `Checklist next`, and `Required env: missing` was only run during focused verification.
- Variant: run `npm.cmd --prefix apps/dashboard test -- --run` from `ops/hooks/pre-push` and assert that the hook keeps it wired.
- Primary KPI: future pushes fail before merge when the dashboard UI no longer renders credential-boundary or operator-checklist states covered by `apps/dashboard/src/App.test.jsx`.
- Guardrails: keep the deterministic Python smoke bundle, credential handoff checks, MCP runtime probes, workflow gates, completion audit, and objective coverage in place.

## Adopted Variant

Adopted. The pre-push hook now runs the dashboard Vitest suite after the Python smoke bundle and before credential/runtime probes. `tests/test_pre_push_hook.py` asserts the dashboard UI command remains wired.

## Hook Command Correction

The first pushed hook used `cmd.exe /c "cd apps\\dashboard && npm test -- --run"`. The real Git hook showed that Git's MSYS shell did not pass that form as intended: `cmd.exe` consumed the pre-push ref line instead of reliably running Vitest. The adopted command is now `npm.cmd --prefix apps/dashboard test -- --run`, which was verified under Git's `sh.exe` and PowerShell.

## Changed Paths

- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`

## Verification

- `cmd /c "cd apps\dashboard && npm test -- --run"` -> `9 passed`
- `C:\Program Files\Git\usr\bin\sh.exe -c 'npm.cmd --prefix apps/dashboard test -- --run'` -> `9 passed`
- `npm.cmd --prefix apps/dashboard test -- --run` -> `9 passed`
- `python -m pytest tests\test_pre_push_hook.py -q` -> `6 passed`
- `python ops\hooks\install_hooks.py --check` -> hook current
- `python ops\scripts\autoresearch_completion_audit.py` -> `38` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py` -> `7` requirements, `cycle_prompt_covered=true`, `global_objective_complete=false`

## Remaining Boundary

This strengthens local regression protection for the dashboard UI. It does not complete credential-gated Canva OAuth/OpenAPI execution, GitHub high-volume live refresh with a token, Telegram delivery, OTLP collector shipping, or hosted runtime/tracing operator decisions.

global_objective_complete=false
