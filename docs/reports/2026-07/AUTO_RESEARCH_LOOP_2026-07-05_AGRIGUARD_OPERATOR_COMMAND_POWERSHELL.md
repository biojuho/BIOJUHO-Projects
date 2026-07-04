# AutoResearch Loop: AgriGuard Operator Command PowerShell Format

Date: 2026-07-05

## Objective

Make operator-facing Markdown command lists use the same explicit PowerShell call-operator format as artifact recovery commands.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: operator instructions should be directly executable from the shell named by the command contract.

## A/B Contract

- Baseline: artifact recovery commands used `& ...` PowerShell text, while operator-packet safe rerun commands and handoff operator Markdown commands could render as plain command strings.
- Variant: render operator-packet command strings with `& ...` and render handoff Markdown command lists from the same PowerShell argv formatter.
- Primary KPI: commands copied from operator packet Markdown and handoff Markdown run from `%TEMP%`.
- Guardrails: keep JSON argv arrays unchanged, keep existing command ordering and paths, preserve schema validation, and keep workspace/browser smoke green.
- Decision: adopt. Operator packet and handoff Markdown command lists now use explicit PowerShell invocation text.

## Changed Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_OPERATOR_COMMAND_POWERSHELL.md`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` - `22 passed`.
- Real copy-paste proof:
  - Rendered `var\agriguard-operator-command-powershell-proof\operator-powershell-operator-packet.md`.
  - Extracted the first safe rerun command for `validate_launch_env_template.py` and ran it from `%TEMP%`: exit code `0`.
  - Rendered `var\agriguard-operator-command-powershell-proof\operator-powershell-handoff.md`.
  - Extracted the `inspect_status` operator command and ran it from `%TEMP%`: exit code `0`.
  - Confirmed both commands start with `& ` and quote `D:\AI project\apps\AgriGuard`.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` - `61 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-command-powershell.json` - `passed=5`, `failed=0`, elapsed `4m59s`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-operator-command-powershell.json --output-dir var\agriguard-browser-smoke-suite-operator-command-powershell --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The operator-facing command path is now consistent once that file is supplied.

## Next Cycle

Audit launch-readiness summaries for command shell metadata so downstream clients can distinguish PowerShell command text from plain labels.
