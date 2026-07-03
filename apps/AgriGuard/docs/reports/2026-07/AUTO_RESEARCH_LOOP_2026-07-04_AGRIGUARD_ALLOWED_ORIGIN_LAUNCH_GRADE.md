# AgriGuard AutoResearch Loop - launch-grade allowed origins

Date: 2026-07-04

## Objective

Close a launch-preflight gap where `AGRIGUARD_ALLOWED_ORIGINS` only needed to be
present. A strict compose launch could be made to pass with localhost or plain
HTTP CORS origins, which is not launch-grade for a public consumer verification
surface.

## Scope and owned paths

- `scripts/launch_env_preflight.py`
- `backend/tests/test_launch_env_preflight.py`

Dirty pre-existing README and env-example changes were left untouched.

## A/B hypothesis and decision rule

Baseline: strict preflight rejected missing and wildcard allowed origins, but
accepted insecure or loopback origins if they were explicitly set.

Variant: strict preflight validates each allowed origin as HTTPS, host-bearing,
pathless, queryless, fragmentless, and non-loopback. Local smoke checks can opt
in with `--allow-local-allowed-origins`.

Decision rule: adopt only if focused tests, synthetic preflight evidence, and
the canonical AgriGuard smoke scope all pass.

## Evidence

- Pass: `python -m py_compile scripts/launch_env_preflight.py backend/tests/test_launch_env_preflight.py`
- Pass: `python -m pytest backend/tests/test_launch_env_preflight.py -q --basetemp "..\var\tmp\pytest-agriguard-origin-grade"` (`53 passed`)
- Expected fail-closed: `python scripts/launch_env_preflight.py --json-out "..\var\agriguard-launch-env-preflight-origin-grade-local-origin-fail.json"` with synthetic `AGRIGUARD_ALLOWED_ORIGINS=http://localhost:5174` wrote two launch blockers:
  - `AGRIGUARD_ALLOWED_ORIGINS origin 'http://localhost:5174' must use an https:// URL for launch.`
  - `AGRIGUARD_ALLOWED_ORIGINS origin 'http://localhost:5174' must not use a local host for launch.`
- Pass: same synthetic env with `--allow-local-allowed-origins` wrote `..\var\agriguard-launch-env-preflight-origin-grade-local-origin-override.json` with status `pass`.
- Pass: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-origin-grade.json"` (`passed=5`, `failed=0`, `total=5`)

## Current launch blocker

Docker is ready on this machine. The strict Docker-backed launch preflight wrote
`..\var\agriguard-launch-env-preflight-origin-grade-current.json` with Docker
daemon and compose config checks passing. It still fails closed because the
current local env has not supplied these app-scoped launch values:

- `AGRIGUARD_SECRET_KEY`
- `AGRIGUARD_QR_TOKEN_PEPPER`
- `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`
- `AGRIGUARD_ALLOWED_ORIGINS`

The two secret values can be generated and stored locally or in the deployment
secret store, but they should not be committed. `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`
and `AGRIGUARD_ALLOWED_ORIGINS` require the real public HTTPS deployment origin;
inventing a placeholder domain would make the preflight misleading.

## Decision

Adopt the stricter allowed-origin variant. AgriGuard now refuses launch preflight
success for development CORS origins unless the caller explicitly declares a
local diagnostic run.

## Next cycle

Continue with launch evidence once the operator supplies the public HTTPS verify
base URL and frontend/API allowed origins. After those values exist, rerun
`python apps/AgriGuard/scripts/launch_env_preflight.py --check-docker --json-out var/agriguard-launch-env-preflight.json`
from the workspace root before treating compose as launch-ready.
