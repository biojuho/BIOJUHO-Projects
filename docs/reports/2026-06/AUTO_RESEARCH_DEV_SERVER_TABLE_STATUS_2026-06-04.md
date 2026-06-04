# AutoResearch Dev-Server Table Status - 2026-06-04

## Source-Backed Candidate

- Source: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
- Radar gap: dev-server status was machine-readable and dashboard-visible, but terminal operators still had only a one-line summary unless they opened JSON.
- Local constraint: preserve the existing summary output and JSON artifact contract.

## Adopted Variant

- Added `--format table` to `ops/scripts/dev_server_status.py`.
- Added `--format json` for stdout JSON when `--json-out` is not convenient.
- Kept the default `summary` output unchanged, including `--validate-only`.
- Added `format_status_table()` with stable columns:
  - `target`
  - `project`
  - `kind`
  - `state`
  - `status`
  - `latency`
  - `error`
- Updated `docs/guides/dev-server-control.md`.
- Added tests in `tests/test_dev_server_status.py`.

## Verification

- `python -m pytest tests\test_dev_server_status.py -q -p no:cacheprovider`
  - `12 passed`
- `python -m compileall -q ops\scripts\dev_server_status.py`
  - passed
- `python ops\scripts\dev_server_status.py --target canva-widget-preview --timeout 1 --format table --json-out var\dev-server-status-table-canva-2026-06-04.json`
  - printed a target row for `canva-widget-preview`
  - state was `UNREADY`
  - error was `timed out`
  - JSON artifact recorded `ready=0`, `total=1`, `unready=1`

## Remaining Gap

The local CLI now has manifest-backed start, stop, status, tail, dashboard readiness, and a terminal table view. MCP exposure for dev-server operations remains watch-scoped rather than a release blocker.
