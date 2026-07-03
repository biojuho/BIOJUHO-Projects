# AgriGuard AutoResearch Loop - compose auto-create schema env scoping

Date: 2026-07-04

## Source-backed observation

The current local launch preflight showed `AUTO_CREATE_SCHEMA=true` in the host environment. AgriGuard compose already ignores host `DATABASE_URL`, but it still passed host `AUTO_CREATE_SCHEMA` into the backend container, which could enable schema creation during a launch by accident.

## Adopted variant

- Changed compose to pass `AUTO_CREATE_SCHEMA=${AGRIGUARD_AUTO_CREATE_SCHEMA:-false}` into the backend container.
- Updated launch preflight compose mode to validate `AGRIGUARD_AUTO_CREATE_SCHEMA` instead of host `AUTO_CREATE_SCHEMA`.
- Kept direct runtime preflight validation against `AUTO_CREATE_SCHEMA`, matching direct backend startup behavior.
- Added tests proving compose mode ignores host `AUTO_CREATE_SCHEMA` while direct mode still rejects it.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-auto-create-scope"` (`36 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
- Checked rendered compose includes `AUTO_CREATE_SCHEMA: "false"` with the current host environment.
- Pass: current local compose-mode preflight rerun wrote `var/agriguard-launch-env-preflight-current.json` with status `pass`.
