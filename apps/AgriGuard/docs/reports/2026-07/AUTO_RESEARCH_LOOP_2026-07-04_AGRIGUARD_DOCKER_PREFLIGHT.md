# AgriGuard AutoResearch Loop - Docker launch preflight

Date: 2026-07-04

## Source-backed observation

The current AgriGuard environment preflight passed after app-scoped compose env hardening, but live compose startup still had an unclassified external blocker: Docker Desktop's Linux engine was not reachable. A launch operator needs this surfaced by the same fail-closed preflight, not only by an attempted `docker info` in chat.

## Adopted variant

- Added `--check-docker` to `apps/AgriGuard/scripts/launch_env_preflight.py`.
- The Docker check runs `docker info --format "{{.ServerVersion}}"` and `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`.
- The report fails closed when the daemon is unreachable or compose config validation fails.
- Added unit coverage for skipped Docker checks, passing Docker checks, daemon failure, and compose config failure.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-docker-preflight-2"` (`14 passed`)
- Pass: env-only preflight wrote `var/agriguard-launch-env-preflight-current-continuation.json` with status `pass`.
- Expected fail-closed: `python apps/AgriGuard/scripts/launch_env_preflight.py --check-docker --json-out var/agriguard-launch-env-preflight-docker-current.json` returned status `fail` because Docker daemon is not reachable.
- Docker compose config still passed inside the same `--check-docker` report, so the Docker-specific blocker is engine availability rather than YAML/config shape.
- Later strict origin preflight now also blocks launch when `AGRIGUARD_ALLOWED_ORIGINS` is unset. Use `--allow-runtime-default-origins` only when intentionally isolating Docker readiness from production-origin configuration.
