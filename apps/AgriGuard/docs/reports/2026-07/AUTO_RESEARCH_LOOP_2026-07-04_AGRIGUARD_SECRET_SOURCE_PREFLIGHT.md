# AgriGuard AutoResearch Loop - secret source preflight

Date: 2026-07-04

## Source-backed observation

AgriGuard compose can bridge `AGRIGUARD_SECRET_KEY` into backend `SECRET_KEY`, but direct backend startup reads `SECRET_KEY` itself. The launch preflight previously accepted whichever variable was present first, which could overstate readiness for either runtime.

## Adopted variant

- Compose runtime now requires app-scoped `AGRIGUARD_SECRET_KEY` by default.
- Direct runtime now requires backend `SECRET_KEY`.
- `--allow-generic-secret-key` keeps an explicit local escape hatch for compose checks that intentionally accept generic `SECRET_KEY`.
- Added unit coverage for compose default rejection, compose local override, and direct runtime secret-source alignment.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-secret-source-preflight-2"` (`24 passed`)
- Expected fail-closed: current strict preflight wrote `var/agriguard-launch-env-preflight-secret-source-current.json` with status `fail` because `AGRIGUARD_SECRET_KEY` and `AGRIGUARD_ALLOWED_ORIGINS` are not set.
- Pass: current local override preflight with `--allow-runtime-default-origins --allow-generic-secret-key` wrote `var/agriguard-launch-env-preflight-secret-source-local-override.json` with status `pass` and the missing-origin warning.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-secret-source-docker-current.json` with three launch blockers: missing `AGRIGUARD_SECRET_KEY`, missing `AGRIGUARD_ALLOWED_ORIGINS`, and unavailable Docker daemon.
