# AutoResearch Loop - AgriGuard Frontend Dockerignore

Date: 2026-07-04
App: AgriGuard
Cycle: Frontend Docker build context hardening

## Baseline

The frontend Docker context excluded `node_modules`, `dist`, env files, editor folders, and logs. The working frontend directory also contains local build outputs and browser test artifacts such as `build_agri.out`, `build_out.txt`, `build_err.txt`, and `test-results/`.

Risk:

- Local artifacts can be copied into the Docker build context.
- Build contexts become larger and less reproducible.
- Test output can leak into production image build inputs.

## Variant

Expanded `apps/AgriGuard/frontend/.dockerignore` to exclude:

- `coverage/`
- `playwright-report/`
- `test-results/`
- local build output files
- npm/yarn debug logs
- `.DS_Store`

Added a config test to keep these exclusions in place.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-frontend-dockerignore"`
  - Result: 9 passed

## Decision

Adopt the expanded frontend Docker ignore rules. The production build context is now cleaner and less sensitive to local test/build residue.
