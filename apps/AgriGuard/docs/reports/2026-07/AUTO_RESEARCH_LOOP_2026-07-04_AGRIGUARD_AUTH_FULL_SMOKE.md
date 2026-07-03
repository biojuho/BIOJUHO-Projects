# AgriGuard AutoResearch Loop - auth full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after auth launch-preflight hardening:

- `d78c27f` Block AgriGuard dev auth launch toggles.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-auth-preflight-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m57s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`467 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-auth-preflight-2026-07-04.json`.
- Strict launch preflight now loads backend `.env` plus app `.env`, rejects dev/test auth toggles, and requires app-scoped launch secrets, QR pepper, public verify URL, allowed origins, and launch-grade database credentials.
- Strict `--check-docker` launch preflight remains externally blocked until Docker Desktop's Linux engine is running.
