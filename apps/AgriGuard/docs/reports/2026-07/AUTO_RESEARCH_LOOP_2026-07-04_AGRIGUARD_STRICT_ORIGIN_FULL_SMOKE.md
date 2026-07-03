# AgriGuard AutoResearch Loop - strict origin full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after strict launch-origin preflight hardening:

- `4579db4` Require explicit AgriGuard launch origins.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-strict-origin-preflight-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m54s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`437 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-strict-origin-preflight-2026-07-04.json`.
- Strict env-only launch preflight now fails closed until `AGRIGUARD_ALLOWED_ORIGINS` is set.
- `--allow-runtime-default-origins` remains available for local checks that intentionally accept runtime default origins.
