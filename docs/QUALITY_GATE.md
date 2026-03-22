# Workspace Quality Gate

This document defines the deterministic quality gate for this workspace.

## Scope

- Included: `desci-platform`, `AgriGuard`, `DailyNews`, `notebooklm-mcp`, `github-mcp`, `getdaytrends`

## Local Commands

Run from repository root:

```bash
python scripts/run_workspace_smoke.py --scope all
python scripts/run_workspace_smoke.py --scope workspace
python scripts/run_workspace_smoke.py --scope desci
python scripts/run_workspace_smoke.py --scope agriguard
python scripts/run_workspace_smoke.py --scope mcp
python scripts/run_workspace_smoke.py --scope getdaytrends
python scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
```

## Deterministic PR Gate

The PR gate includes only checks that are deterministic and reproducible without external credentials:

- `desci`
  - frontend: lint, unit tests, `build:lts`, bundle budget
  - biolinker: smoke pytest
- `workspace`
  - regression tests: `tests/test_workspace_regressions.py`, `tests/test_workspace_smoke.py`
- `agriguard`
  - frontend: lint, `build:lts`
  - backend: python compile smoke
- `mcp`
  - python compile smoke for tracked MCP code paths
  - `DailyNews/tests/unit` pytest suite
- `getdaytrends`
  - python compile smoke
  - `getdaytrends/tests` pytest suite

Python compile checks explicitly exclude these directories:

- `.agent`
- `.agents`
- `venv`
- `__pycache__`
- `output`

## External Integration Tests Policy

Tests that require live services, credentials, or internet access are out of the default PR gate.

- Keep them tagged as integration and/or external.
- Run them manually or in separate scheduled/on-demand workflows.
- Do not block standard PR merges on external flakiness.

## JSON Report Schema

`scripts/run_workspace_smoke.py --json-out <path>` writes an array of check results with:

- `scope`
- `name`
- `cwd`
- `command`
- `returncode`
- `ok`
- `stdout_tail`
- `stderr_tail`
