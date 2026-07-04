# AutoResearch Loop: Fail-Closed Compose Launch Wrapper

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the normal compose launch path run strict launch preflight before starting containers, so operators do not have to manually remember the preflight and compose command ordering.

## Baseline

The repository had a strict `launch_env_preflight.py` checker and README guidance to run it before `docker compose up`. There was no repo-owned launch command that enforced that order, so an operator could still start compose with development defaults or missing Firebase credentials.

## Variant Tested

Add `scripts/launch_compose.py`:

- Builds a strict preflight command with `--check-docker`.
- Writes preflight JSON to `var/agriguard-launch-env-preflight-compose-launch.json` by default.
- Stops before `docker compose up` when preflight returns non-zero.
- Runs `docker compose -f docker-compose.yml up -d --build` only after preflight passes.
- Supports repeated `--service` values for scoped launches.
- Supports `--dry-run` for a command plan without starting anything.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_compose_script.py -q --basetemp "..\var\tmp\pytest-agriguard-launch-compose-wrapper"
```

Result: `3 passed in 0.32s`.

Dry-run wrapper plan:

```powershell
python scripts/launch_compose.py --dry-run --json-out "..\var\agriguard-launch-compose-wrapper-dry-run-preflight.json" --service backend
```

Result: printed preflight first, then `docker compose -f ... up -d --build backend`.

Current fail-closed wrapper run:

```powershell
python scripts/launch_compose.py --json-out "..\var\agriguard-launch-compose-wrapper-current-preflight.json"
```

Result: expected exit code `1`. The wrapper wrote the strict preflight report, Docker daemon and compose config checks passed, and the wrapper printed `docker compose up was not run`.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-launch-compose-wrapper.json"
```

Result: `passed=5, failed=0, total=5`.

## Remaining Launch Blocker

The wrapper now prevents accidental compose startup with the current incomplete launch environment. Real launch still requires the operator-provided Firebase Admin service-account file, app-scoped launch secrets, public HTTPS verify URL, and allowed origins.
