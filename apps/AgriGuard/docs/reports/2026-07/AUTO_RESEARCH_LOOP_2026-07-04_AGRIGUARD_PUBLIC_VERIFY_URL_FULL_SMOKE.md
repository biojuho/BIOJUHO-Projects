# AgriGuard AutoResearch Loop - public verify URL full smoke

Date: 2026-07-04

## Scope

Refreshed branch-tip AgriGuard evidence after public QR verify URL launch-preflight hardening:

- `fd054e7` Require AgriGuard public verify URL preflight.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-public-url-preflight-2026-07-04.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m20s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`458 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-public-url-preflight-2026-07-04.json`.
- Strict launch preflight now fails closed until `AGRIGUARD_SECRET_KEY`, `AGRIGUARD_QR_TOKEN_PEPPER`, `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and `AGRIGUARD_ALLOWED_ORIGINS` are set.
- Strict `--check-docker` launch preflight also remains blocked until Docker Desktop's Linux engine is running.
