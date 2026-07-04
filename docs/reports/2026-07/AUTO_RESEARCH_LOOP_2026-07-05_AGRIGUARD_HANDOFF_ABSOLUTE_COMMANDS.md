# AutoResearch Loop: AgriGuard Handoff Absolute Commands

Date: 2026-07-05

## Objective

Make copied guarded-launch handoff commands independent of the operator's current working directory. The handoff already carried enough artifact paths, but `inspect_status`, `require_ready`, and validation commands were emitted as workspace-root-relative commands.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: recovery and status commands should be copyable, deterministic, and bound to explicit artifact paths.

## A/B Contract

- Baseline: handoff commands used `python apps/AgriGuard/scripts/...`, so copied commands depended on running from the workspace root.
- Variant: emit `sys.executable`, resolved script paths, explicit `--app-root`, absolute `--output-dir`, and absolute status/validation output paths.
- Primary KPI: embedded handoff commands run from `%TEMP%` and still inspect blocked status, fail closed on `--require-ready`, and validate the handoff.
- Guardrails: blocked missing-Firebase launch remains blocked; handoff validation schema still passes; workspace smoke and browser suite pass.
- Decision: adopt. Handoff commands are now cwd-independent.

## Changed Paths

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q` - `13 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var\agriguard-handoff-absolute-command-proof --output-prefix handoff-absolute-command-proof --emit-handoff` - expected exit `1`; handoff consumer `errors=[]`, artifact index `status=pass`.
- Embedded `inspect_status` command from `%TEMP%` - exit `0`, status output remained `blocked`.
- Embedded `require_ready` command from `%TEMP%` - expected exit `1`, wrote `handoff-absolute-command-proof-ready-gate.json`.
- Embedded validation command from `%TEMP%` - exit `0`, handoff valid.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` - `46 passed`.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q` - `12 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-absolute-commands.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-handoff-absolute-commands.json --output-dir var\agriguard-browser-smoke-suite-handoff-absolute-commands --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The local handoff commands now remain usable when copied from the artifact directory or another shell location.

## Next Cycle

Continue auditing operator packets for commands that still assume workspace-root cwd or default artifact paths.
