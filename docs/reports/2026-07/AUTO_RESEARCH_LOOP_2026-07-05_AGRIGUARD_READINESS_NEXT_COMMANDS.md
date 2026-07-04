# AutoResearch Loop: AgriGuard Readiness Next Commands

Date: 2026-07-05

## Objective

Upgrade the launch readiness summary from prose-only next actions to copyable next commands sourced from the operator packet's safe rerun commands.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: blocked launch summaries should preserve machine-readable, copyable recovery commands instead of forcing operators to reconstruct commands from prose.

## A/B Contract

- Baseline: readiness summaries listed next actions as prose only.
- Variant: include `next_commands` entries derived from `operator_packet.safe_rerun_commands`, with stable names for env validation, guarded launch, strict preflight, and compose launch.
- Primary KPI: a real missing-Firebase readiness summary includes four copyable commands while preserving `preflight_blocked` status.
- Guardrails: no secrets exposed, existing next-action prose remains, launch report and operator-packet tests continue to pass, workspace smoke and browser smoke remain green.
- Decision: adopt. Readiness summaries now expose copyable commands for blocked launch states.

## Changed Paths

- `apps/AgriGuard/scripts/summarize_launch_readiness.py`
- `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_READINESS_NEXT_COMMANDS.md`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` - `6 passed`.
- `python apps/AgriGuard/scripts/summarize_launch_readiness.py --app-root apps/AgriGuard --launch-report-json var\agriguard-launch-report-app-root-command-proof\launch-report-app-root-command-proof-launch-report.json --env-validation-json var\agriguard-launch-report-app-root-command-proof\launch-report-app-root-command-proof-env-validation.json --operator-packet-json var\agriguard-launch-report-app-root-command-proof\launch-report-app-root-command-proof-operator-packet.json --json-out var\agriguard-readiness-next-commands-proof.json --markdown-out var\agriguard-readiness-next-commands-proof.md --exit-zero-on-blocked` - pass; generated `validate_env_template`, `guarded_launch`, `strict_preflight`, and `compose_launch` next commands.
- `python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q` - `56 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-readiness-next-commands.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-readiness-next-commands.json --output-dir var\agriguard-browser-smoke-suite-readiness-next-commands --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The readiness summary now gives the operator copyable commands after they provide that external file.

## Next Cycle

Audit artifact index recovery command rendering for shell-safe copyability and direct replay from non-root working directories.
