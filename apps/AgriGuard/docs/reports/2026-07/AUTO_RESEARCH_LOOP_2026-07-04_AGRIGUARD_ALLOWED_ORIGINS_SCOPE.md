# AgriGuard AutoResearch Loop - allowed origins preflight scoping

Date: 2026-07-04

## Source-backed observation

AgriGuard compose passes backend CORS origins from `AGRIGUARD_ALLOWED_ORIGINS`, with a compose default when it is unset. The launch preflight still accepted generic host `ALLOWED_ORIGINS` in compose mode, which could make a local shell look more launch-configured than the compose container would be.

## Adopted variant

- Updated compose-mode launch preflight to read only `AGRIGUARD_ALLOWED_ORIGINS`.
- Kept direct runtime preflight compatible with direct backend startup by accepting `ALLOWED_ORIGINS` when `AGRIGUARD_ALLOWED_ORIGINS` is not set.
- Added checks that compose mode ignores host `ALLOWED_ORIGINS`, direct mode accepts it, and app-scoped wildcard origins fail closed.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-allowed-origins-scope"` (`17 passed`)
- Pass: current local env-only preflight wrote `var/agriguard-launch-env-preflight-current-continuation.json` with status `pass` and warning `No explicit allowed origins configured; runtime defaults may be used.`
- Expected fail-closed: current local `--check-docker` preflight still fails only because Docker daemon is not reachable; compose config remains valid.
