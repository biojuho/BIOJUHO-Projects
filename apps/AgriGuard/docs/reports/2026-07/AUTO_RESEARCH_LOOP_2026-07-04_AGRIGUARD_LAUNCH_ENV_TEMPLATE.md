# AutoResearch Loop: Launch Env Template

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make a blocked compose-launch attempt produce a redacted `.env` template with
the exact launch variable shape, placeholder markers, and safe auth flags.

## Scope and Owned Paths

- `scripts/render_launch_operator_packet.py`
- `scripts/launch_compose.py`
- `backend/tests/test_render_launch_operator_packet.py`
- `backend/tests/test_launch_compose_script.py`

The broader worktree is dirty from unrelated ongoing work, so this cycle staged
only these AgriGuard-owned files and this report.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` main:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local modernization radar:
  `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-env-template.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_ENV_TEMPLATE.md`
  reported `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`.

The adopted source-backed pattern is fail-closed operator handoff: blocked
automation should write precise, redacted, machine-readable and human-readable
next-action evidence without making the blocked launch look successful.

## A/B Hypothesis

Baseline: the compose launcher emits an operator packet and Markdown, but the
operator still has to translate action IDs into a launch `.env` shape.

Variant: the packet renderer writes an optional dotenv template, and
`launch_compose.py` emits it by default on preflight failure. The template
contains placeholders only, production-safe auth flags, and a warning to replace
all `<...>` values before rerunning preflight.

Primary KPI: one failed launch-wrapper run produces an aggregate report whose
operator-packet summary records `env_template_found=true` and the template path.

Decision rule: adopt if focused tests cover template content, live fail-closed
launch writes the template and embeds it in the aggregate report, and canonical
AgriGuard smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_render_launch_operator_packet.py backend/tests/test_launch_compose_script.py -q
```

Result: `14 passed in 0.77s`.

Current fail-closed launch-wrapper run:

```powershell
python scripts/launch_compose.py --run-browser-smoke --json-out ..\var\agriguard-launch-compose-env-template-preflight.json --launch-report-json ..\var\agriguard-compose-launch-env-template-report.json --operator-packet-json ..\var\agriguard-launch-compose-env-template-packet.json --operator-packet-markdown ..\var\agriguard-launch-compose-env-template-packet.md --operator-env-template ..\var\agriguard-launch-compose.env.template
```

Result: expected exit code `1`. Docker daemon and compose config checks passed,
compose was not run, packet rendering succeeded, and the aggregate report
embedded:

- `child_reports.operator_packet.status`: `blocked`
- `child_reports.operator_packet.secrets_redacted`: `true`
- `child_reports.operator_packet.env_template_found`: `true`
- `child_reports.operator_packet.env_template_variables`: includes
  `AGRIGUARD_DB_PASSWORD`, `AGRIGUARD_ALLOWED_ORIGINS`,
  `AGRIGUARD_SECRET_KEY`, `AGRIGUARD_QR_TOKEN_PEPPER`,
  `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`,
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, `ALLOW_TEST_BYPASS`, and
  `ALLOW_DEV_AUTH_FALLBACK`.

The generated template includes placeholder-only sensitive values and
launch-safe flags:

- `AGRIGUARD_SECRET_KEY=<set-strong-secret-32-plus-chars>`
- `AGRIGUARD_QR_TOKEN_PEPPER=<set-stable-qr-token-pepper-32-plus-chars>`
- `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>`
- `ALLOW_TEST_BYPASS=false`
- `ALLOW_DEV_AUTH_FALLBACK=false`

Dry-run command plan:

```powershell
python scripts/launch_compose.py --run-browser-smoke --dry-run
```

Result: plan includes `operator_env_template` and passes
`--env-template-out` to `render_launch_operator_packet.py`.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-env-template.json
```

Result: `passed=5`, `failed=0`, `total=5`; elapsed `5m29s`.

## Adopt Decision

Adopt the launch env-template artifact. This reduces the remaining external
operator blocker from a prose checklist to a concrete, redacted file shape while
preserving preflight as the authority that rejects placeholders and missing
production values.

## Remaining Launch Blocker

The generated template still requires operator-provided real values before a
live compose/browser launch can pass:

- A real Firebase Admin service-account JSON path outside the repo.
- Strong `AGRIGUARD_SECRET_KEY`.
- Stable strong `AGRIGUARD_QR_TOKEN_PEPPER`.
- HTTPS `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`.
- Explicit production `AGRIGUARD_ALLOWED_ORIGINS`.
- Strong database password or PostgreSQL `AGRIGUARD_DATABASE_URL`.

## Next Cycle

Use the generated template as input to a shape-only preflight fixture so
operators can validate that all placeholders have been replaced before any
compose retry.
