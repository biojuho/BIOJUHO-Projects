# AutoResearch Dev-Server Group Stop - 2026-06-04

## Outcome

The manifest-backed dev-server controller now supports a one-command teardown for a frontend and its declared dependency chain. Operators can run `stop --target <frontend> --include-dependencies` to stop the requested target first and then stop its dependencies in manifest order, with a structured JSON summary.

## Adopted Changes

- Added `stop_target_group` to `ops/scripts/dev_server_control.py`.
- Added `stop_order_with_dependencies` with cycle detection and duplicate suppression.
- Added compact grouped stop JSON fields: `stop_order`, `summary`, and per-target `results`.
- Kept existing single-target `stop` behavior unchanged unless `--include-dependencies` is passed.
- Treat missing dependency state as `not_managed` for grouped stops, so optional dependencies that were not controller-managed do not break teardown.

## Live Operator Proof

- Start command:
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-start-dashboard-group-stop-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  - Result: `dev server ready: dashboard-frontend pid=22176, attempts=2`
- Stop command:
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-stop-dashboard-group-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 5`
  - Result: `dev server group stopped: dashboard-frontend stopped=2/2`
- Stop order: `dashboard-frontend`, `dashboard-api`
- Final status:
  - `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard-after-group-stop-2026-06-04.json`
  - Result: `0/2 ready`
- Direct port check: no listeners remained on `8080` or `5173`.

## Verification

- `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py -q -p no:cacheprovider` -> `20 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-dev-server-group-stop-2026-06-04.json` -> `8/8 PASS`

## Remaining Boundary

This cycle adds dependency-aware stop for an explicit target. It does not add bulk stop by project or tag; that can be added later if repeated multi-target sessions need a broader operator command.
