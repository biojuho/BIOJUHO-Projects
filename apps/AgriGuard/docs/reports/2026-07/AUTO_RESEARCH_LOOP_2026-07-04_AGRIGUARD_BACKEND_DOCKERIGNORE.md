# AutoResearch Loop - AgriGuard Backend Dockerignore

Date: 2026-07-04
App: AgriGuard
Cycle: Backend Docker build context hardening

## Baseline

The backend Docker context ignored Python bytecode, pytest cache, coverage, env files, and databases. The working backend directory also contains local runtime/test artifacts such as `.venv/`, `.deepeval/`, `*.egg-info/`, `var/`, `tests/`, and `test_api.py`.

Risk:

- Local virtual environments and test artifacts can be sent to Docker builds.
- Build contexts become larger and less reproducible.
- Test-only files can enter production image build inputs.

## Variant

Expanded `apps/AgriGuard/backend/.dockerignore` to exclude:

- `.venv/` and `venv/`
- `*.egg-info/`
- `.deepeval/`
- `var/`
- `tests/`
- `test_*.py`

Added a config test to keep backend Docker context exclusions in place.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-backend-dockerignore"`
  - Result: 10 passed

## Decision

Adopt the expanded backend Docker ignore rules. The production backend build context is now cleaner and less sensitive to local runtime/test residue.
