# Dev-Server Control Guide

Use the manifest-backed dev-server controller for browser QA, local operator checks, and repeatable start/stop evidence. Targets are declared in `ops/references/dev_server_targets.json`; each target has a stable id, command, readiness URL, expected response markers, and optional dependencies.

## Quick Status

Validate the manifest without probing live ports:

```powershell
python ops\scripts\dev_server_status.py --validate-only
```

Check all configured targets:

```powershell
python ops\scripts\dev_server_status.py --json-out var\dev-server-status.json
```

Check one stack:

```powershell
python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dev-server-status-dashboard.json
```

## Start A Browser Stack

Start a frontend and its declared dependencies:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-start.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3
```

The same pattern works for the product frontends:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-start.json start --target desci-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 5
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-agriguard-start.json start --target agriguard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3
```

For Canva preview:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-canva-start.json start --target canva-widget-preview --wait-ready --wait-timeout 60 --poll-interval 2 --timeout 2
```

## Tail Logs

Capture recent stdout and stderr:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-tail.json tail --target dashboard-frontend --lines 80
```

## Stop A Stack

Stop a frontend and its declared dependencies in one command:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-stop.json stop --target dashboard-frontend --include-dependencies --timeout 10
```

The grouped stop order is the requested target first, then its dependency chain. This prevents a frontend from keeping a proxy or HMR session alive while its API is being stopped.

For single services or previews without dependencies:

```powershell
python ops\scripts\dev_server_control.py --json-out var\dev-server-control-canva-stop.json stop --target canva-widget-preview --timeout 5
```

## Evidence Checklist

For a browser QA cycle, save these artifacts:

- Start JSON from `dev_server_control.py start`.
- Browser console/network evidence and screenshot from Playwright or the browser probe.
- Tail JSON if a runtime issue was observed.
- Stop JSON from `dev_server_control.py stop`.
- Final `dev_server_status.py` JSON showing the intended targets are ready or stopped.
- The affected smoke scope JSON from `ops\scripts\run_workspace_smoke.py`.

## Current Target IDs

- `dashboard-api`
- `dashboard-frontend`
- `agriguard-api`
- `agriguard-frontend`
- `desci-api`
- `desci-frontend`
- `canva-widget-preview`

Use `--target` with these ids. Add new ids only through `ops/references/dev_server_targets.json` and cover manifest behavior in `tests/test_dev_server_status.py` or `tests/test_dev_server_control.py`.
