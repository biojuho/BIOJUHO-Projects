# AutoResearch Dev-Server Wait-Ready Probe - 2026-06-04

## Scope

- Surface: `ops/scripts/dev_server_status.py`
- Baseline: the dev-server probe could produce a one-time readiness snapshot, but browser automation still needed an external retry loop to wait for a target to become available.
- Variant adopted: add `--wait-ready`, `--wait-timeout`, and `--poll-interval` so the manifest-backed probe can wait for selected targets before an app-click/browser pass begins.

## Changed Paths

- `ops/scripts/dev_server_status.py`
- `tests/test_dev_server_status.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_WAIT_READY_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- existing snapshot and validate-only behavior still works,
- wait mode retries an initially offline target until it becomes ready,
- wait mode respects a zero-timeout degraded path,
- the CLI works against a real local target,
- the relevant focused tests and workspace smoke scope pass.

## Evidence

- Syntax:
  - `python -m py_compile ops\scripts\dev_server_status.py`
  - Result: passed.
- Focused tests:
  - `python -m pytest tests\test_dev_server_status.py -q -p no:cacheprovider`
  - Result: `8` passed.
- Live wait-ready CLI:
  - `python ops/scripts/dev_server_status.py --target agriguard-api --wait-ready --wait-timeout 5 --poll-interval 0.5 --timeout 1 --json-out var/dev-server-status-agriguard-api-wait-2026-06-04.json`
  - Result: `1/1` ready, `0` unready, `attempts=1`.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-dev-server-wait-ready-2026-06-04.json`
  - Result: passed `8/8`.

## Remaining Launch Work

- Add process start/stop and log-tail orchestration as a separate cycle once operator-visible usage confirms the wait-ready contract.
