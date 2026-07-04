# AutoResearch Loop: Env Example Test Bypass Guard

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the app-level env example consistent with the fail-closed launch preflight
by disabling the active `ALLOW_TEST_BYPASS` assignment. Operators who copy
`.env.example` should not inherit a launch-forbidden auth bypass.

## Scope and Owned Paths

- `.env.example`
- `backend/tests/test_cors_origins.py`

The app env example still has unrelated pre-existing unstaged additions in the
worktree. This cycle owns only the active `ALLOW_TEST_BYPASS=false` hunk and the
regression test that parses active, uncommented env assignments.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` main:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The relevant source-backed pattern is fail-closed completion evidence: examples
used by operators should not carry a bypass that the launch gate later rejects.

## A/B Hypothesis

Baseline: app `.env.example` sets `ALLOW_TEST_BYPASS=true`. The preflight blocks
that value for launch, but a copied example guarantees an avoidable failure.

Variant: set `ALLOW_TEST_BYPASS=false` and add a regression check that parses
active env assignments, ignoring commented local-diagnostic examples.

Primary KPI: preflight report for `.env.example` has
`forbidden_launch_flags_enabled=[]`.

Decision rule: adopt if the focused env/docs test passes, example preflight no
longer reports forbidden launch flags, and canonical AgriGuard smoke remains
green.

## Evidence

Focused contract test:

```powershell
python -m pytest backend/tests/test_cors_origins.py -q
```

Result: `32 passed, 1 warning in 4.22s`.

Env-example preflight:

```powershell
python scripts/launch_env_preflight.py --env-file .env.example --allow-local-public-verify-base-url --allow-local-allowed-origins --allow-missing-firebase-credentials --json-out ..\var\agriguard-launch-env-preflight-env-example-test-bypass-guard.json
```

Result: expected `status=fail` for placeholders and local HTTP, but
`forbidden_launch_flags_enabled=[]`. Remaining errors were placeholder
`AGRIGUARD_SECRET_KEY`, placeholder `AGRIGUARD_QR_TOKEN_PEPPER`, local HTTP
`AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and placeholder `AGRIGUARD_DB_PASSWORD`.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-env-example-test-bypass-guard.json
```

Result: `passed=5`, `failed=0`, `total=5`; elapsed `5m25s`.

## Adopt Decision

Adopt the env-example guard. This removes one avoidable local configuration
failure from the operator launch path while preserving the explicit commented
dev-auth fallback example for local diagnostics.

## Remaining Launch Blocker

The example now avoids launch-forbidden auth bypasses, but real launch still
requires operator-provided strong secrets, a real Firebase service-account JSON
path, HTTPS public verify URL, and explicit production origins.
