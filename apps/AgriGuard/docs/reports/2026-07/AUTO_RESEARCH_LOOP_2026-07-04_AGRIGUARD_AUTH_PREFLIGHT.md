# AgriGuard AutoResearch Loop - auth preflight

Date: 2026-07-04

## Source-backed observation

The backend loads `backend/.env` during auth/database startup, and compose also mounts that file through `env_file`. The launch preflight previously loaded only the app-level `.env`, so it could miss backend-local launch blockers. It also did not fail closed on dev/test authentication toggles.

## Adopted variant

- Default preflight env loading now reads `apps/AgriGuard/backend/.env` first and `apps/AgriGuard/.env` second, matching compose's backend env-file plus app-level interpolation override pattern.
- Launch preflight now rejects `ALLOW_TEST_BYPASS=true`.
- Launch preflight now rejects `ALLOW_DEV_AUTH_FALLBACK=true`.
- Launch preflight now rejects any configured `DEV_AUTH_FALLBACK_ROLE`.
- The launch report records forbidden auth flags and whether the dev fallback role is set without exposing secret values.
- The README launch checklist now calls out disabled dev/test auth toggles.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-auth-preflight"` (`47 passed`, 2 warnings)
- Pass: synthetic app-scoped launch env with auth toggles forced off wrote `var/agriguard-launch-env-preflight-auth-pass.json` with status `pass`.
- Expected fail-closed: synthetic app-scoped launch env with `ALLOW_TEST_BYPASS=true` wrote `var/agriguard-launch-env-preflight-auth-test-bypass-fail.json` with status `fail`.
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`.
- Expected fail-closed: current strict preflight wrote `var/agriguard-launch-env-preflight-auth-current.json` with status `fail` because app-scoped launch values are not fully set.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-auth-docker-current.json` with the same missing app-scoped launch values plus unavailable Docker daemon.
