# AutoResearch Loop - AgriGuard Launch Hardening Smoke

Date: 2026-07-04
App: AgriGuard
Cycle: Aggregate launch-hardening verification

## Context

After the compose and nginx hardening slices, the first full AgriGuard smoke run was killed by the command timeout while the backend suite was still running.

Partial result before timeout:

- Frontend lint: pass
- Frontend build: pass
- Contracts compile: pass
- Contracts tests: pass
- Backend tests: still running

The backend suite was then reproduced directly with the same async pytest plugin used by the smoke runner:

- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with fastapi --with sqlalchemy --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-backend-launch-hardening-async"`
  - Result: 407 passed, 2 warnings
  - Elapsed: 270.81s

## Full Smoke Evidence

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-launch-hardening-2026-07-04-complete.json`

Result:

- Status: pass
- Passed: 5/5
- Failed: 0
- Total elapsed: 5m31s
- Slowest check: `agriguard backend tests`, 4m51s

Covered checks:

- `agriguard frontend lint`
- `agriguard frontend build`
- `agriguard contracts compile`
- `agriguard contracts tests`
- `agriguard backend tests`

## Refresh After Compose Hardening

After the optional backend env file, compose secret bridge, and Mosquitto persistence-volume changes, the full AgriGuard smoke was rerun:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-launch-hardening-2026-07-04-final.json`

Result:

- Status: pass
- Passed: 5/5
- Failed: 0
- Total elapsed: 4m9s
- Slowest check: `agriguard backend tests`, 3m32s

## Decision

Use the completed smoke result as the aggregate verification for the July 4 launch-hardening loop. The backend suite is valid but takes longer than the earlier 5-minute command timeout, so future full AgriGuard smoke invocations should allow at least 10 minutes.
