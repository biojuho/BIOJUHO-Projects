# AutoResearch Loop: AgriGuard Readiness Command Shell Metadata

Date: 2026-07-05

## Objective

Add shell metadata to launch-readiness `next_commands` so downstream clients can distinguish PowerShell command text from unlabeled command strings.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: operator-facing command artifacts should include enough metadata for replay tools and humans to choose the correct shell.

## A/B Contract

- Baseline: readiness summaries exposed `next_commands` as `{name, command}` only, even after operator commands became explicit PowerShell command text.
- Variant: infer `shell: "powershell"` for commands that begin with PowerShell `&`, and render that shell in Markdown next to the command label.
- Primary KPI: a real readiness summary built from an operator packet with `& ...` commands exposes four `next_commands`, each with `shell=powershell`, and Markdown shows `(powershell)`.
- Guardrails: existing command labels and command text remain unchanged, non-PowerShell command strings are not mislabeled, and workspace/browser smoke remain green.
- Decision: adopt. Readiness summaries now carry shell metadata for PowerShell command text.

## Changed Paths

- `apps/AgriGuard/scripts/summarize_launch_readiness.py`
- `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_READINESS_COMMAND_SHELL.md`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` - `6 passed`.
- Real summarizer proof:
  - Input packet: `var\agriguard-operator-command-powershell-proof\operator-powershell-operator-packet.json`.
  - Output JSON: `var\agriguard-readiness-next-command-shell-proof.json`.
  - Output Markdown: `var\agriguard-readiness-next-command-shell-proof.md`.
  - Result: status `blocked`, blocker class `operator_values_required`, `4` next commands, all `shell=powershell`, all commands start with `& `, and Markdown includes `(powershell)`.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` - `61 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-readiness-command-shell.json` - `passed=5`, `failed=0`, elapsed `3m29s`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-readiness-command-shell.json --output-dir var\agriguard-browser-smoke-suite-readiness-command-shell --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The readiness summary now labels the shell for the commands the operator runs after supplying that external file.

## Next Cycle

Audit whether launch reports should summarize command-shell metadata in their child report summaries for one-file handoff consumption.
