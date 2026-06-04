# AutoResearch Dev-Server Group Stop - 2026-06-04

## Scope

- Surface: manifest-backed dev-server lifecycle cleanup.
- Baseline: dependency-aware `start` could launch a frontend and API together, but cleanup still required manual stop ordering. A clean-worktree dashboard proof also showed the dashboard API readiness marker was too data-dependent: `/api/quality_overview` returned `200` with stable structural fields but no `workspace_smoke` key when optional data DBs were absent.
- Variant adopted: add `stop --include-dependencies` and relax the dashboard API readiness marker to stable structural fields: `qa_grades` and `daily_production`.

## Changed Paths

- `ops/references/dev_server_targets.json`
- `ops/scripts/dev_server_control.py`
- `tests/test_dev_server_control.py`
- `tests/test_dev_server_status.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_GROUP_STOP_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- grouped stop recursively stops dependency state recorded during managed start,
- dashboard API readiness remains valid even when optional workspace-smoke evidence is absent,
- a real managed dashboard stack starts and `stop --include-dependencies` clears both frontend and API ports,
- focused tests and workspace smoke pass.

## Evidence

- Focused tests:
  - `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py -q -p no:cacheprovider`
  - Result: `18` passed.
- Real dashboard stack start:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-group-stop-start-fixed-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 45 --poll-interval 0.75 --timeout 1`
  - Result: `dashboard-frontend` ready, `attempts=3`; `dashboard-api` was started first as a dependency.
- Grouped stop:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-group-stop-stop-fixed-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 10`
  - Result: frontend `status=stopped`; JSON included `dependency_stops: [{target_id: "dashboard-api", status: "stopped"}]`.
- Cleanup verification:
  - `python ops/scripts/dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var/dev-server-status-dashboard-after-group-stop-fixed-2026-06-04.json`
  - Result: `0/2` ready after stop, with no `LISTENING` sockets on ports `8080` or `5173`.
- Workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-group-stop-final-2026-06-04.json`
  - Result: passed `6/6`.

## Remaining Launch Work

- Promote grouped start/stop examples into a short operator runbook if repeated browser passes need handoff-friendly commands.
