# AutoResearch Dev-Server Control - 2026-06-04

## Scope

- Surface: manifest-backed local dev-server operations for browser automation.
- Baseline: readiness probes could wait for an already-running target, but operators still had to manually start matching API/frontend stacks and inspect logs. A frontend-only start also looked HTTP-ready while proxying to a missing API.
- Variant adopted: add `ops/scripts/dev_server_control.py` with `start`, `stop`, and `tail`; add frontend `depends_on` metadata; make status downgrade frontends when required APIs are unready; start dependencies by default from the control CLI; clear logs per managed start unless `--append-logs` is requested.

## Changed Paths

- `ops/references/dev_server_targets.json`
- `ops/scripts/dev_server_control.py`
- `ops/scripts/dev_server_status.py`
- `tests/test_dev_server_control.py`
- `tests/test_dev_server_status.py`
- `apps/dashboard/src/hooks/useFetch.js`
- `apps/dashboard/src/hooks/useFetch.test.jsx`
- `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_CONTROL_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- manifest dependency metadata validates,
- status reports a frontend as unready when its API dependency is offline,
- process control writes state, starts dependencies before frontends, tails logs, and stops Windows child listeners by managed port if the parent PID exits,
- the dashboard hook no longer aborts already-completed fetch controllers on later refresh,
- a real dashboard stack start reaches `2/2` readiness and stops cleanly,
- focused tests and the canonical workspace smoke pass.

## Evidence

- Syntax:
  - `python -m py_compile ops\scripts\dev_server_status.py ops\scripts\dev_server_control.py`
  - Result: passed.
- Focused Python tests:
  - `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py -q -p no:cacheprovider`
  - Result: `16` passed.
- Focused dashboard hook test:
  - `npm.cmd run test -- src/hooks/useFetch.test.jsx`
  - Result: `1` test file passed, `1` test passed.
- Real dependency-aware stack start:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-stack-fresh-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 45 --poll-interval 0.75 --timeout 1`
  - Result: `dashboard-frontend` ready, `attempts=2`; `dashboard-api` was started first from `depends_on`.
- Stack readiness:
  - `python ops/scripts/dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var/dev-server-status-dashboard-stack-fresh-ready-2026-06-04.json`
  - Result: `2/2` ready.
- Log tail:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-frontend-fresh-tail-2026-06-04.json tail --target dashboard-frontend --lines 40`
  - Result: fresh frontend `stderr` was empty; no previous `ECONNREFUSED 127.0.0.1:8080` proxy errors after dependency-aware start.
- Browser click pass:
  - Headless Playwright opened `http://127.0.0.1:5173/`, clicked the theme button and refresh button, and saved `var/dashboard-stack-browser-click-pass-fixed-2026-06-04.png`.
  - Result: no console errors and no page errors. Request-failed events were limited to `net::ERR_ABORTED` fetch cancellations under the React StrictMode dev runtime; the fresh server logs showed no API proxy failures.
- Stop/cleanup:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-frontend-final-stack-stop-2026-06-04.json stop --target dashboard-frontend --timeout 10`
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-dashboard-api-final-stack-stop-2026-06-04.json stop --target dashboard-api --timeout 10`
  - Result: both stopped; final status for `dashboard-api` and `dashboard-frontend` was `0/2` ready and no `LISTENING` sockets remained on `8080` or `5173`.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-dev-server-control-2026-06-04.json`
  - Result: passed `8/8`.

## Remaining Launch Work

- Extend the dependency-aware browser pass to AgriGuard, DeSci, and Canva widget targets with the same managed start/stop path.
- Add optional grouped stop by dependency chain if repeated multi-target sessions make manual stop ordering noisy.
