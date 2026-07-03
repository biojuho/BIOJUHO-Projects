# AgriGuard AutoResearch Loop - origin scope full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after direct allowed-origin launch-preflight scoping:

- `ff42c40` Scope AgriGuard direct allowed origins preflight.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-origin-scope-preflight-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m1s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`469 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-origin-scope-preflight-2026-07-04.json`.
- Strict launch preflight now scopes allowed origins by runtime: `AGRIGUARD_ALLOWED_ORIGINS` for compose and `ALLOWED_ORIGINS` for direct backend launch.
- Strict `--check-docker` launch preflight remains externally blocked until Docker Desktop's Linux engine is running.
