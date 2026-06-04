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
python ops/scripts/run_workspace_smoke.py --scope desci --check-timeout 420 --json-out smoke-desci.json
```
For live browser QA and local dev-server lifecycle evidence, use
`docs/guides/dev-server-control.md`.

When an npm-based smoke check runs in a clean worktree, the runner installs
lockfile-backed Node dependencies with `npm ci --no-audit` if `node_modules` is
missing for that package directory. Dependency artifacts are local runtime state
and must not be staged.

Use `--check-timeout <seconds>` when the shell, CI job, or agent tool has its own
outer timeout. Set the smoke runner's check timeout lower than the outer timeout
so `run_workspace_smoke.py` can terminate the child process tree itself and
write partial JSON evidence.

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
Use `--mcp-trace-out <path>` when a scheduled or manual MCP run needs a
standalone JSONL event stream for external trace consumers. The JSONL file is
also refreshed after each completed check and contains one
`workspace_smoke.mcp_check` event per completed MCP check. Non-MCP scopes write
an empty trace file when the flag is supplied.
Use `--mcp-otel-out <path>` when the same MCP evidence needs an
OpenTelemetry Protocol file-exporter style JSONL object. The file is opt-in,
refreshed after each completed check, contains one `resourceSpans` object with
MCP check spans, and stays local/offline unless an operator ships it to a
collector.
Before a collector or scheduled shipper consumes this file, validate the
operator handoff contract:

```bash
python ops/scripts/mcp_otel_collector_handoff.py --otel-jsonl var/workspace-smoke-mcp-otel-handoff-2026-06-05.otlp.jsonl --json-out docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json --markdown-out docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md
```

The handoff check validates the local OTLP JSONL shape and required
`workspace_smoke.*` attributes. It deliberately keeps live collector runtime,
endpoint credentials, retention, sampling, and retry policy future-scoped until
an operator owns those choices.

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
- `started_at_unix_nano`
- `ended_at_unix_nano`

Each `--mcp-trace-out` JSONL event contains:

- `schema_version`
- `event_type` (`workspace_smoke.mcp_check`)
- `generated_at`
- `scope`
- `name`
- `cwd`
- `command`
- `command_kind`
- `returncode`
- `ok`
- `elapsed_seconds`
- `stdout_tail`
- `stderr_tail`

Each `--mcp-otel-out` JSONL line follows the OpenTelemetry Protocol file
exporter shape:

- top-level `resourceSpans`
- resource attributes including `service.name=workspace-smoke`
- `scopeSpans[].scope.name=workspace_smoke.mcp`
- one span per completed MCP check, named `workspace_smoke.mcp_check <check>`
- span `traceId`, `spanId`, `parentSpanId`, `kind`, `startTimeUnixNano`,
  `endTimeUnixNano`, `attributes`, and `status`
- smoke attributes under the `workspace_smoke.*` namespace, including scope,
  check name, working directory, command, command kind, return code, pass/fail
  state, and elapsed seconds
