# AutoResearch Loop: AgriGuard Recovery Command Text Propagation

Date: 2026-07-05

## Objective

Propagate shell-safe artifact-index recovery command text from status-only output into guarded-launch handoff and consumer surfaces without changing the validated `recovery_summary` object.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: recovery instructions should be machine-readable for validators and copyable for operators across every handoff surface.

## A/B Contract

- Baseline: artifact-index Markdown had a copyable command, but status-only JSON, handoff packet validation, and handoff consumer JSON only exposed status/note/summary fields.
- Variant: add sibling `artifact_index_recovery_command_shell` and `artifact_index_recovery_command_text` fields to status and handoff packet-validation surfaces, and mirror them into the consumer view.
- Primary KPI: a real missing-artifact-index handoff validates against the strict schema and exposes the same PowerShell command text in status view, packet validation, Markdown, and consumer JSON.
- Guardrails: keep `recovery_summary` unchanged, keep schema validation strict, do not expose secrets, and keep workspace/browser smoke green.
- Decision: adopt. The command text now survives status-only, handoff, and consumer paths.

## Changed Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_RECOVERY_COMMAND_TEXT_PROPAGATION.md`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q` - `35 passed`.
- Real propagation proof:
  - Rendered `var\agriguard-handoff-recovery-command-text-proof\recovery-text-operator-packet.json`.
  - Rendered and validated `var\agriguard-handoff-recovery-command-text-proof\recovery-text-handoff.json`.
  - Consumed `var\agriguard-handoff-recovery-command-text-proof\recovery-text-handoff.consumer.json`.
  - Result: handoff validation `pass`, consumer errors `0`, command shell `powershell`.
  - Confirmed the same `& ... run_guarded_launch.py ...` command text exists in status view, packet validation, handoff Markdown, and consumer JSON.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q` - `55 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-recovery-command-text-propagation.json` - `passed=5`, `failed=0`, elapsed `5m20s`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-recovery-command-text-propagation.json --output-dir var\agriguard-browser-smoke-suite-recovery-command-text-propagation --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. Recovery command text now guides the operator back through the guarded launch path once that external file is supplied.

## Next Cycle

Audit whether operator-facing Markdown command lists should use the same explicit PowerShell call-operator format as artifact recovery commands.
