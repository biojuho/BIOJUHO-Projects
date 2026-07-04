# AutoResearch Loop: AgriGuard Handoff Command Shells

Date: 2026-07-05

## Objective

Preserve operator command shell metadata in the human-readable guarded-launch handoff Markdown.

## Source Evidence

- Veritas AutoResearch source checked with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Latest observed `main` commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local radar evidence remains `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md` with 8 adopted source-backed patterns.

## A/B Contract

Baseline: handoff JSON carried `command_shell="powershell"` for `inspect_status` and `require_ready`, and artifact-index Markdown rendered shell labels, but handoff Markdown rendered the commands as `` `inspect_status`: `& ...` `` and `` `require_ready`: `& ...` `` without the shell.

Variant: render operator commands in handoff Markdown with the same shell label pattern used by readiness and artifact-index Markdown: `` `command_id` (powershell): `command_text` ``.

Primary KPI: generated handoff Markdown contains shell labels for both operator commands and no longer contains the old unlabeled command lines.

Decision rule: adopt only if focused renderer tests, expanded launch-readiness tests, the real guarded wrapper, workspace smoke, browser smoke, and AgriGuard smoke all pass while strict launch still fails closed only on the missing external Firebase service-account file.

Decision: adopted.

## Owned Paths

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_HANDOFF_COMMAND_SHELLS.md`

## Variant Evidence

- `render_guarded_launch_handoff.py` now appends ` (powershell)` when `command_shell` is present for each operator command.
- `test_render_guarded_launch_handoff.py` now requires the shell label for both `inspect_status` and `require_ready`.

Real guarded wrapper:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-handoff-command-shells --emit-handoff --status-json-out var\agriguard-handoff-command-shells-status.json
```

Result: exited `1` as expected because strict launch remains blocked by the missing real Firebase Admin service-account JSON.

JSON proof:

```json
{"blockerErrors":["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."],"status":"blocked","indexStatus":"pass","consumerCommandMetadata":"pass","inspectStatusShellLabel":true,"requireReadyShellLabel":true,"oldInspectStatusWithoutShell":false,"oldRequireReadyWithoutShell":false}
```

## Verification

- `python -m py_compile apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` passed.
- `python -m ruff check apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py -q` passed: 4 tests.
- Expanded launch-readiness suite passed: 164 tests.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-handoff-command-shells.json` passed: 9/9.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-handoff-command-shells-browser-smoke.json --output-dir var\agriguard-handoff-command-shells-browser-smoke --timeout-ms 120000` passed: 6/6 suites, 135/135 checks, 18/18 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-command-shells.json` passed: 5/5.

## External Blocker

Handoff Markdown command-shell labeling is locally green. Full strict launch remains blocked until an operator supplies a real outside-repo Firebase Admin service-account JSON for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue checking human-readable handoff and artifact-index Markdown for command metadata, stale paths, and missing recovery context.
