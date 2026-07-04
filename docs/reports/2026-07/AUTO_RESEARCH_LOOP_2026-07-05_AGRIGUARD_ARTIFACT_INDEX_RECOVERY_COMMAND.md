# AutoResearch Loop: AgriGuard Artifact Index Recovery Command

Date: 2026-07-05

## Objective

Make guarded-launch artifact-index recovery commands copyable from Markdown and replayable from a non-root working directory.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: human recovery instructions should be directly executable, while machine-readable argv arrays remain stable for validators and downstream tools.

## A/B Contract

- Baseline: `index_guarded_launch_artifacts.py` stored a recovery argv list, but Markdown rendered it with plain space-joining. Paths such as `D:\AI project` were not shell-safe when copied.
- Variant: preserve the existing `recovery_command` argv list and add PowerShell-specific `recovery_command_shell` plus `recovery_command_text`; render Markdown from the formatted command text.
- Primary KPI: the Markdown recovery command can be copied and run from `%TEMP%`, then regenerates guarded-launch artifacts while failing closed on the expected missing Firebase service-account file.
- Guardrails: `recovery_summary` remains schema-compatible, no secrets are emitted, existing handoff/operator consumers continue to pass, workspace smoke and browser smoke remain green.
- Decision: adopt. Artifact-index Markdown now exposes a PowerShell copy-paste command with quoted paths and an explicit call operator.

## Changed Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_ARTIFACT_INDEX_RECOVERY_COMMAND.md`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `8 passed`.
- Real replay proof:
  - Generated `var\agriguard-artifact-index-recovery-command-proof-index.md`.
  - Extracted `Recovery command` from Markdown.
  - Replayed it from `%TEMP%`.
  - Result: exit code `1`, expected because the active operator env still lacks the external Firebase Admin service-account JSON.
  - Confirmed regenerated artifacts: `var\agriguard-artifact-index-recovery-command-proof\shell-safe-recovery-launch-report.json` and `var\agriguard-artifact-index-recovery-command-proof\shell-safe-recovery-artifact-index.json`.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q` - `54 passed`.
- First `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-recovery-command.json` timed out at `180s` with `4/5` checks complete and `0` failures.
- Retry `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-recovery-command-retry.json` - `passed=5`, `failed=0`, elapsed `6m32s`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-artifact-index-recovery-command.json --output-dir var\agriguard-browser-smoke-suite-artifact-index-recovery-command --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The recovery command now takes the operator back into the guarded launch path after that file is provided.

## Next Cycle

Audit status-only and handoff surfaces for whether they should expose the same copyable command text without expanding the validated `recovery_summary` schema.
