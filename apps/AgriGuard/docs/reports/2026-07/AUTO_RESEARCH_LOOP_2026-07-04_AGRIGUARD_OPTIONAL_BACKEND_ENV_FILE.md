# AutoResearch Loop - AgriGuard Optional Backend Env File

Date: 2026-07-04
App: AgriGuard
Cycle: Clean-checkout compose readiness

## Baseline

The app compose file referenced the local backend env file as a required file:

`env_file: ./backend/.env`

That file is ignored by the workspace `.gitignore`.

Risk:

- A fresh checkout can fail compose startup before containers are created because `apps/AgriGuard/backend/.env` is intentionally not tracked.
- Local operator overrides are useful, but they should not be required for the default compose contract.

## Variant

Changed the backend env file declaration to the explicit optional form:

```yaml
env_file:
  - path: ./backend/.env
    required: false
```

The compose file still provides explicit defaults for the backend environment, including `ENV`, `DATABASE_URL`, `AUTO_CREATE_SCHEMA`, `ALLOWED_ORIGINS`, MQTT host/port, and `PYTHONPATH`.

Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-optional-backend-env"`
  - Result: 18 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the optional local env file. Clean checkouts can parse and start from checked-in compose defaults, while developers can still add `backend/.env` for local overrides.
