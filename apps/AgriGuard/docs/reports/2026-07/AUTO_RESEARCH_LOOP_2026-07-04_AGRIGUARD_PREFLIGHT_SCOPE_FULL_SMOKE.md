# AgriGuard AutoResearch Loop - preflight scope full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after launch preflight hardening:

- `1b05eec` Add AgriGuard Docker launch preflight.
- `4e06f09` Scope AgriGuard allowed origins preflight.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-preflight-scope-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m23s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`434 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-preflight-scope-2026-07-04.json`.
- Current env-only launch preflight passes with a warning that no app-scoped `AGRIGUARD_ALLOWED_ORIGINS` is set.
- Current `--check-docker` launch preflight fails closed only because Docker Desktop's Linux engine is unavailable; compose config validation passes.
