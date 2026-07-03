# AgriGuard AutoResearch Loop - secret source full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after app-scoped launch-secret preflight hardening:

- `8521d88` Require app-scoped AgriGuard launch secret.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-secret-source-preflight-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m1s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`441 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-secret-source-preflight-2026-07-04.json`.
- Strict launch preflight now fails closed until `AGRIGUARD_SECRET_KEY` and `AGRIGUARD_ALLOWED_ORIGINS` are set.
- Strict `--check-docker` launch preflight also remains blocked until Docker Desktop's Linux engine is running.
- `--allow-runtime-default-origins --allow-generic-secret-key` remains available only for local checks that intentionally accept runtime defaults.
