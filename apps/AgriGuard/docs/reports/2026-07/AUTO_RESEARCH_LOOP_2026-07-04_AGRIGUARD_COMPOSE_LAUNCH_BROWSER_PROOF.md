# AutoResearch Loop: Compose Launch Browser Proof

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Extend the fail-closed compose launcher so a real launch command can optionally prove the browser workflow after compose startup, instead of requiring operators to remember a separate browser-smoke command.

## Scope and Owned Paths

- `scripts/launch_compose.py`
- `backend/tests/test_launch_compose_script.py`

## A/B Hypothesis

Baseline: `scripts/launch_compose.py` runs strict preflight, then `docker compose up -d --build`, and stops there.

Variant: add `--run-browser-smoke` so the launcher:

1. Runs strict preflight.
2. Runs `docker compose up -d --build --wait`.
3. Runs `scripts/run_browser_smoke_suite.py` against compose defaults.

Primary KPI: fewer manual launch-verification steps while preserving fail-closed ordering.

Decision rule: adopt only if default behavior is unchanged, dry-run clearly shows the additional command, browser smoke runs only after compose succeeds, current missing operator config still stops before compose/browser smoke, and canonical smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_compose_script.py -q --basetemp "..\var\tmp\pytest-agriguard-launch-compose-browser-smoke"
```

Result: `6 passed in 0.37s`.

Dry-run command plan:

```powershell
python scripts/launch_compose.py --run-browser-smoke --browser-smoke-mobile --dry-run --json-out "..\var\agriguard-launch-compose-browser-smoke-dry-run-preflight.json" --browser-smoke-json-out "..\var\agriguard-browser-smoke-suite-compose-launch-dry-run.json" --browser-smoke-output-dir "..\var\agriguard-browser-smoke-suite-compose-launch-dry-run"
```

Result: command plan includes:

- `launch_env_preflight.py --check-docker`
- `docker compose -f ... up -d --build --wait`
- `run_browser_smoke_suite.py --base-url http://127.0.0.1 --api-url http://127.0.0.1:8002 ... --mobile`

Current fail-closed launch run:

```powershell
python scripts/launch_compose.py --run-browser-smoke --json-out "..\var\agriguard-launch-compose-browser-smoke-current-preflight.json" --browser-smoke-json-out "..\var\agriguard-browser-smoke-suite-compose-launch-current.json"
```

Result: expected exit code `1`. Docker daemon and compose config checks passed, but strict preflight stopped before compose/browser smoke because operator launch values are still missing.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-launch-compose-browser-smoke.json"
```

Result: `passed=5, failed=0, total=5`.

## Adopt Decision

Adopt `--run-browser-smoke`. The launcher now supports one command for preflight, waited compose startup, and aggregate browser proof while preserving the default preflight-plus-compose behavior.

## Remaining Launch Blocker

The browser proof cannot pass on this machine until a real Firebase Admin service-account file, app-scoped launch secrets, public HTTPS verify URL, and allowed origins are provided.
