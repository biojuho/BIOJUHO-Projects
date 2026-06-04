# Workspace Quality Gate

This document defines the deterministic quality gate for the active workspace.

## Active scope

Included units:

- `apps/desci-platform`
- `apps/AgriGuard`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `automation/content-intelligence`
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
python ops/scripts/run_workspace_smoke.py --scope cie
python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
```
For live browser QA and local dev-server lifecycle evidence, use
`docs/guides/dev-server-control.md`.

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
  - contracts compile and tests
  - biolinker smoke pytest
- `agriguard`
  - frontend lint and build
  - contracts compile and tests
  - backend pytest suite
- `mcp`
  - compile smoke for tracked MCP paths
  - `automation/DailyNews/tests/unit` pytest suite
- `getdaytrends`
  - python compile smoke
  - `automation/getdaytrends/tests` pytest suite
- `cie`
  - python compile smoke
  - `automation/content-intelligence/tests` pytest suite

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

`run_workspace_smoke.py --json-out <path>` writes a schema-v1 object. The
runner refreshes the file after each completed check, so a crash or timeout in a
later check leaves a `partial` report with the finished checks preserved.

Top-level fields:

- `schema_version`
- `generated_at`
- `status` (`partial` or `complete`)
- `duration_seconds`
- `summary` (`total`, `completed`, `passed`, `failed`, `remaining`)
- `scope_summary` (per completed scope: `completed`, `passed`, `failed`, `elapsed_seconds`)
- `mcp_trace` (MCP-specific smoke evidence: `enabled`, counts, elapsed time, checked units, command kinds, and per-check status)
- `results`

Each `results` entry contains:

- `scope`
- `name`
- `cwd`
- `command`
- `returncode`
- `ok`
- `stdout_tail`
- `stderr_tail`
- `elapsed_seconds`
