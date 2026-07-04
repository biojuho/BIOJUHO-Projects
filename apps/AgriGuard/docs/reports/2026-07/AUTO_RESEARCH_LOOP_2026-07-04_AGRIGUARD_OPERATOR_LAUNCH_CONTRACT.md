# AutoResearch Loop: Operator Launch Contract

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Align the operator-facing launch instructions and env example with the new
fail-closed compose launcher so an operator does not follow the stale raw
`docker compose up` path or miss the compose-only Firebase credential setting.

## Scope and Owned Paths

- `.env.example`
- `README.md`
- `backend/tests/test_cors_origins.py`

Existing broader README and env-example edits were already present in the
worktree. This cycle owns only the launch-wrapper, Firebase env example, and
regression-test hunks.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` main:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern remains bounded continuous improvement with durable status,
same-sample A/B checks, and fail-closed completion evidence.

## A/B Hypothesis

Baseline: README quick start leads with raw `docker compose up -d postgres
mosquitto backend frontend`, and `.env.example` has generic
`GOOGLE_APPLICATION_CREDENTIALS` but not
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. The current launcher then fails
closed correctly, but the operator-facing setup path does not advertise the
required wrapper or compose credential variable.

Variant: make `python scripts/launch_compose.py --run-browser-smoke` the quick
start compose command, document the aggregate report, add
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=backend/firebase-service-account.json`
to the app env example, and add text-level tests for the README/env contract.

Primary KPI: first-run operator launch path reaches the strict launcher by
default and exposes the required compose Firebase credential variable before
preflight.

Decision rule: adopt if the focused contract test passes, launcher dry-run shows
preflight plus compose wait plus browser smoke, and canonical AgriGuard smoke
remains green.

## Evidence

Focused contract test:

```powershell
python -m pytest backend/tests/test_cors_origins.py -q
```

Result: `31 passed, 1 warning in 4.58s`.

Launcher dry-run:

```powershell
python scripts/launch_compose.py --run-browser-smoke --dry-run
```

Result: `status=dry_run`, `will_run_compose_after_preflight=true`,
`will_run_browser_smoke_after_compose=true`, compose command includes
`up -d --build --wait`, and default launch report is
`D:\AI project\var\agriguard-compose-launch-report.json`.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-compose-launch-docs.json
```

The tool wrapper timed out at 184 seconds, but the spawned smoke process
continued and completed. Final JSON status:
`complete`, `passed=5`, `failed=0`, `total=5`; backend tests reported
`505 passed, 2 warnings in 257.79s`.

## Adopt Decision

Adopt the operator-launch contract change. It does not unblock a real launch by
itself, but it prevents the documented path from bypassing the launcher that now
aggregates preflight, compose, and browser-smoke evidence.

## Remaining Launch Blocker

Real compose/browser launch still requires operator-provided production values:

- `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` pointing at a real Firebase Admin
  service-account JSON outside the repo.
- Strong `AGRIGUARD_SECRET_KEY` and `AGRIGUARD_QR_TOKEN_PEPPER`.
- HTTPS `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`.
- Explicit production `AGRIGUARD_ALLOWED_ORIGINS`.
