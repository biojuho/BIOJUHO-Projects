# AutoResearch Dev-Server Status Probe - 2026-06-04

## Scope

- Surface: workspace operator/dev-server readiness
- Baseline: the modernization radar identified `Uninen/devserver-mcp` as a comparable pattern for process monitoring, browser automation, and operator-facing runtime status, but this workspace had no unified manifest-backed live dev-server readiness probe.
- Variant adopted: add a repo-local dev-server target manifest and a schema-v1 probe CLI that validates target metadata, checks local HTTP status, verifies service-specific body markers, and writes machine-readable readiness evidence.

## External Sources Checked

- `Uninen/devserver-mcp`: `https://github.com/Uninen/devserver-mcp`
- `evalstate/fast-agent`: `https://github.com/evalstate/fast-agent`

## Changed Paths

- `ops/references/dev_server_targets.json`
- `ops/scripts/dev_server_status.py`
- `tests/test_dev_server_status.py`
- `ops/references/github_modernization_sources.json`
- `docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_STATUS_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- the manifest validates against real repo-relative target directories,
- target URLs are constrained to explicit local HTTP(S) ports,
- shell command separators and unsafe evidence paths are rejected,
- probes can distinguish the expected service from a wrong service on the same port using body markers,
- the CLI can write schema-v1 JSON evidence without failing just because optional dev servers are stopped,
- the modernization radar still validates after adding the new evidence paths.

## Evidence

- Syntax:
  - `python -m py_compile ops\scripts\dev_server_status.py`
  - Result: passed.
- Focused tests:
  - `python -m pytest tests\test_dev_server_status.py tests\test_github_modernization_radar.py -q -p no:cacheprovider`
  - Result: `9` passed.
- Manifest-only CLI:
  - `python ops\scripts\dev_server_status.py --validate-only --json-out var\dev-server-status-manifest-validate-2026-06-04.json`
  - Result: valid `7` target manifest, no network probe required.
- Live status snapshot:
  - `python ops/scripts/dev_server_status.py --json-out var/dev-server-status-2026-06-04.json --timeout 0.75`
  - Result: `1/7` ready, `6` unready.
  - Ready target: `agriguard-api`, with HTTP `200` and expected body marker `AgriGuard API`.
  - Unready targets are expected when their dev servers are not currently running.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-dev-server-status-2026-06-04-rerun.json`
  - Result: passed `8/8`.
- Modernization radar:
  - `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-dev-server-status-2026-06-04.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Result: `6` sources, `adopted=1`, `partially_adopted=4`, `watch=1`.

## Remaining Launch Work

- Add start/stop/log-tail orchestration only after the manifest-backed probe is exercised by operators.
- Optionally surface the latest `var/dev-server-status-*.json` in the dashboard quality panel as a follow-up UI slice.
