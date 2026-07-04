# AutoResearch Loop - AgriGuard Launch Report Command Shell Metadata - 2026-07-05

## Objective

Preserve shell-labeled readiness rerun commands in the one-file AgriGuard
launch report so downstream operators and clients do not need to open the
separate readiness summary JSON to distinguish PowerShell commands from
unlabeled command strings.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_LAUNCH_REPORT_COMMAND_SHELL.md`

## External Sources Checked

- Veritas AutoResearch source: `Veritas-7/autoresearch-skill-system`
  - Latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
  - Command: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Local modernization radar:
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`
  - Current basis: 8 sources reviewed; adopted=8, partially_adopted=0, watch=0.

## A/B Contract

- Baseline: `launch_compose.py` summarized readiness child reports with
  `next_actions`, but dropped readiness `next_commands`, including the new
  `shell: powershell` metadata.
- Variant: summarize a compact, validated `next_commands` list into
  `launch_report.child_reports.readiness_summary`.
- Primary KPI: the aggregate launch report contains all readiness next commands
  with `name`, `command`, and `shell` fields when the readiness summary emits
  them.
- Guardrails: no unrelated launch report schema changes, stale readiness JSON is
  still ignored when readiness summary generation fails, and canonical AgriGuard
  smoke/browser checks remain green.
- Decision rule: adopt only if focused tests, real blocked launch proof, broader
  guarded-launch tests, workspace smoke, and browser smoke all pass.

## Baseline Evidence

Before the patch, `_summarize_readiness_summary_json()` returned:

- `found`
- `path`
- `status`
- `blocker_class`
- `secrets_redacted`
- `next_actions`

It did not preserve readiness `next_commands`, so the aggregate launch report
lost shell metadata needed for one-file handoff consumption.

## Variant Evidence

`launch_compose.py` now adds `_summarize_readiness_next_commands()` and includes
`next_commands` in the readiness child summary. The helper keeps only valid
command entries and preserves optional `shell` metadata.

Focused fixture coverage now writes PowerShell-labeled readiness commands and
asserts that they appear in `report["child_reports"]["readiness_summary"]`.

## Real CLI Proof

Command:

```powershell
python apps/AgriGuard/scripts/launch_compose.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --validate-env-file-shape --json-out var\agriguard-launch-compose-command-shell-preflight.json --launch-report-json var\agriguard-launch-compose-command-shell-report.json --operator-packet-json var\agriguard-launch-compose-command-shell-operator-packet.json --operator-packet-markdown var\agriguard-launch-compose-command-shell-operator-packet.md --operator-env-template var\agriguard-launch-compose-command-shell-operator.env.template --env-validation-json var\agriguard-launch-compose-command-shell-env-validation.json --env-validation-markdown var\agriguard-launch-compose-command-shell-env-validation.md --readiness-summary-json var\agriguard-launch-compose-command-shell-readiness-summary.json --readiness-summary-markdown var\agriguard-launch-compose-command-shell-readiness-summary.md --service backend
```

Result: exited `1` as expected. Docker and compose config checks passed; strict
preflight remained blocked only because
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a missing service-account
file.

Aggregate launch report proof:

- `status`: `fail`
- `stage`: `preflight`
- `stop_reason`: `preflight_failed`
- `child_reports.readiness_summary.found`: `true`
- `child_reports.readiness_summary.status`: `blocked`
- `child_reports.readiness_summary.blocker_class`: `preflight_blocked`
- `child_reports.readiness_summary.next_commands`: 4
- `next_commands[*].shell`: `powershell,powershell,powershell,powershell`
- `next_commands[*].command` all begin with `& `

Artifacts:

- `var/agriguard-launch-compose-command-shell-report.json`
- `var/agriguard-launch-compose-command-shell-readiness-summary.json`
- `var/agriguard-launch-compose-command-shell-readiness-summary.md`

## Verification Commands

```powershell
python -m py_compile apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_launch_compose_script.py
```

Result: passed.

```powershell
python -m ruff check apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_launch_compose_script.py
```

Result: passed.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py -q
```

Result: `17 passed`.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q
```

Result: `6 passed`.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q
```

Result: `78 passed`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-compose-command-shell.json
```

Result: passed=5, failed=0, total=5.

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-launch-compose-command-shell.json --output-dir var\agriguard-browser-smoke-suite-launch-compose-command-shell --timeout-ms 120000
```

Result: passed=6, failed=0, checks_passed=135/135,
screenshots_passed=18/18.

## Adopt or Reject

Adopted. The variant improves one-file launch report handoff fidelity while the
real blocked launch path remains fail-closed on the existing external Firebase
service-account blocker.

## Commit and Push Status

This report is part of the cycle commit. Final commit and push are performed
after exact-path staging and staged diff checks.

## Remaining Blocker

AgriGuard is still not launch-ready because the real outside-repo Firebase Admin
service-account JSON is missing. Local code, shape validation, Docker daemon,
compose config, workspace smoke, and browser smoke are green for this cycle.

## Next Cycle

Audit whether guarded-launch status and handoff consumers should surface the
readiness `next_commands` shell metadata alongside action IDs so every operator
view exposes the same copy-paste-safe recovery commands.
