# Workspace Quality Gate

This document defines the deterministic quality gate for the active workspace.

## Active scope

Included units:

- `apps/desci-platform`
- `apps/AgriGuard`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `mcp/notebooklm-mcp`
- `mcp/github-mcp`
- `packages/shared`

Excluded by default:

- `archive/**`
- `var/**`
- inactive legacy projects

## Root commands

Canonical commands:

```bash
python ops/scripts/run_workspace_smoke.py --scope all
python ops/scripts/run_workspace_smoke.py --scope workspace
python ops/scripts/run_workspace_smoke.py --scope desci
python ops/scripts/run_workspace_smoke.py --scope agriguard
python ops/scripts/run_workspace_smoke.py --scope mcp
python ops/scripts/run_workspace_smoke.py --scope getdaytrends
python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
```

Legacy compatibility commands remain available after:

```bash
python bootstrap_legacy_paths.py
python scripts/run_workspace_smoke.py --scope all
```

## Deterministic gate contents

- `workspace`
  - `tests/test_workspace_regressions.py`
  - `tests/test_workspace_smoke.py`
  - dashboard frontend lint, unit tests, build, bundle budget
- `desci`
  - frontend lint, unit tests, build, bundle budget
  - biolinker smoke pytest
- `agriguard`
  - frontend lint and build
  - backend pytest suite
- `mcp`
  - compile smoke for tracked MCP paths
  - `automation/DailyNews/tests/unit` pytest suite
- `getdaytrends`
  - python compile smoke
  - `automation/getdaytrends/tests` pytest suite

Python compile checks exclude:

- `.agent`
- `.agents`
- `.venv`
- `__pycache__`
- `archive`
- `var`
- generated output folders

## Policy

External-service tests stay out of the default PR gate. Keep them manual, scheduled, or separately triggered so standard PRs stay deterministic.

## Release Approval Overlay

The deterministic quality gate is a development-health signal. It is not, by itself, a release approval.

Release approval additionally requires:

- a passing deterministic gate for the affected scope,
- a clean worktree or an explicitly reviewed in-progress diff set,
- review of compatibility and deprecation warnings that are still allowed at runtime,
- confirmation of the active source of truth for any feature being released,
- explicit verification of manual or external service steps that the deterministic gate does not cover.

DailyNews rule:

- Treat report status `published` as shorthand for `notion_synced` unless external delivery has been separately verified.

## JSON report schema

`run_workspace_smoke.py --json-out <path>` writes an array of objects containing:

- `scope`
- `name`
- `cwd`
- `command`
- `returncode`
- `ok`
- `stdout_tail`
- `stderr_tail`
