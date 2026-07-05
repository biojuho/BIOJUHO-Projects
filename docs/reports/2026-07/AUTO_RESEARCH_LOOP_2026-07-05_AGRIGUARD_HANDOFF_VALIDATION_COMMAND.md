# AutoResearch Loop: AgriGuard Handoff Validation Command

Date: 2026-07-05

## Objective

Make the guarded-launch handoff Markdown self-validating by rendering the validation command already present in handoff JSON.

## Source Evidence

- Veritas AutoResearch source checked with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Latest observed `main` commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local radar evidence remains `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md` with 8 adopted source-backed patterns.

## A/B Contract

Baseline: handoff JSON exposed `validation.command_shell`, `validation.command_text`, `schema_json`, and `validation_json`, but handoff Markdown did not show that self-validation command.

Variant: add a `Handoff Validation` Markdown section containing schema path, validation output path, command shell, and command text.

Primary KPI: generated handoff Markdown includes the validation section, the PowerShell shell label, the `validate_guarded_launch_handoff.py` command, and the validation JSON output path.

Decision rule: adopt only if focused renderer tests, expanded launch-readiness tests, the real guarded wrapper, workspace smoke, browser smoke, and AgriGuard smoke all pass while strict launch still fails closed only on the missing external Firebase service-account file.

Decision: adopted.

## Owned Paths

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_HANDOFF_VALIDATION_COMMAND.md`

## Variant Evidence

- `render_guarded_launch_handoff.py` now renders `## Handoff Validation`.
- The section includes `schema_json`, `validation_json`, `command_shell`, and `command_text`.
- `test_render_guarded_launch_handoff.py` asserts the section, validation path, shell, and command text.

Real guarded wrapper:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-handoff-validation-command --emit-handoff --status-json-out var\agriguard-handoff-validation-command-status.json
```

Result: exited `1` as expected because strict launch remains blocked by the missing real Firebase Admin service-account JSON.

JSON proof:

```json
{"blockerErrors":["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."],"indexStatus":"pass","consumerCommandMetadata":"pass","validationShell":"powershell","validationCommandText":true,"markdownHasValidationSection":true,"markdownHasValidationShell":true,"markdownHasValidationCommand":true,"markdownHasValidationJson":true}
```

## Verification

- `python -m py_compile apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` passed.
- `python -m ruff check apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py -q` passed: 4 tests.
- Expanded launch-readiness suite passed: 164 tests.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-handoff-validation-command.json` passed: 9/9.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-handoff-validation-command-browser-smoke.json --output-dir var\agriguard-handoff-validation-command-browser-smoke --timeout-ms 120000` passed: 6/6 suites, 135/135 checks, 18/18 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-validation-command.json` passed: 5/5.

## External Blocker

Handoff Markdown validation-command rendering is locally green. Full strict launch remains blocked until an operator supplies a real outside-repo Firebase Admin service-account JSON for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue checking human-readable handoff and artifact-index Markdown for missing operator commands and stale compact status fields.
