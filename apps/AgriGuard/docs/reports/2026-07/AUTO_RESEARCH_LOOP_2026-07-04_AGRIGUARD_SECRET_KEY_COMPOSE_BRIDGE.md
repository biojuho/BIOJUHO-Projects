# AutoResearch Loop - AgriGuard Secret Key Compose Bridge

Date: 2026-07-04
App: AgriGuard
Cycle: Clean-checkout secret propagation

## Baseline

After making `backend/.env` optional, the backend compose service still did not pass `SECRET_KEY` from the app-level compose interpolation environment.

Risk:

- A developer or operator can set `SECRET_KEY` in the compose `.env`, but the backend container may not receive it unless `backend/.env` also exists.
- Optional local env files should not silently drop the session secret expected by the backend.

## Variant

Added explicit backend environment propagation:

`SECRET_KEY=${AGRIGUARD_SECRET_KEY:-${SECRET_KEY:-}}`

This keeps `AGRIGUARD_SECRET_KEY` as the preferred app-scoped override while preserving compatibility with the existing `SECRET_KEY` variable used in the app `.env.example`.

Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-secret-key-compose-bridge"`
  - Result: 19 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the explicit compose secret bridge. Clean-checkout compose can now pass a session secret from checked-in compose interpolation variables even when the ignored backend-local env file is absent.
