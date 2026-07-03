# AgriGuard AutoResearch Loop - strict origin preflight

Date: 2026-07-04

## Source-backed observation

The compose preflight correctly ignored generic host `ALLOWED_ORIGINS`, but still passed when no app-scoped `AGRIGUARD_ALLOWED_ORIGINS` was set. For a launch check, relying on runtime defaults is too weak because the compose defaults are development origins.

## Adopted variant

- Missing explicit allowed origins now fail closed by default.
- `--allow-runtime-default-origins` keeps a deliberate local/dev escape hatch that downgrades the missing-origin condition to a warning.
- Added unit coverage for strict default behavior, the local override, and compose/direct origin-source semantics.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-strict-origin-preflight"` (`20 passed`)
- Expected fail-closed: current env-only preflight wrote `var/agriguard-launch-env-preflight-strict-origin-current.json` with status `fail` because `AGRIGUARD_ALLOWED_ORIGINS` is not set.
- Pass: current `--allow-runtime-default-origins` preflight wrote `var/agriguard-launch-env-preflight-allow-default-origin-current.json` with status `pass` and a missing-origin warning.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-strict-origin-docker-current.json` with two launch blockers: missing `AGRIGUARD_ALLOWED_ORIGINS` and unavailable Docker daemon.
