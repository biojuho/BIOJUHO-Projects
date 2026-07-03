# AgriGuard AutoResearch Loop - env-scope full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after app-scoped launch environment hardening:

- `95c478f` Add AgriGuard launch environment preflight.
- `0250518` Align AgriGuard launch preflight with compose database env.
- `bc1a1ce` Scope AgriGuard compose schema creation env.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-launch-env-scope-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 6m04s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`427 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-launch-env-scope-2026-07-04.json`.
- Current local compose-mode launch preflight also passes after scoping host `DATABASE_URL` and `AUTO_CREATE_SCHEMA` behind AgriGuard-specific env variables.
