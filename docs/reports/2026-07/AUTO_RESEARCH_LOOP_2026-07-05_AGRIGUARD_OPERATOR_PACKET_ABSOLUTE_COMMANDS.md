# AutoResearch Loop: AgriGuard Operator Packet Absolute Commands

Date: 2026-07-05

## Objective

Make AgriGuard launch operator packet safe rerun commands independent of the operator's current working directory. The previous packet still emitted relative `python apps/AgriGuard/scripts/...` commands even after the guarded handoff commands were made cwd-independent.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: operator recovery commands should be copyable from any shell location, bind to explicit artifacts, and fail closed when provider credentials are still missing.

## A/B Contract

- Baseline: `safe_rerun_commands`, `guarded_launch_evidence.wrapper_command`, and missing-index recovery commands used workspace-root-relative script and artifact paths.
- Variant: emit `sys.executable`, resolved script paths, absolute env/output paths, and `--app-root` where supported.
- Primary KPI: all packet safe rerun commands execute from `%TEMP%`; shape validation passes, while guarded launch, strict preflight, and compose launch fail closed on the same missing Firebase service-account file.
- Guardrails: packet markdown/evidence table still validates, handoff consumer remains clean, workspace smoke passes, and browser smoke passes.
- Decision: adopt. The operator packet now emits cwd-independent safe rerun commands.

## Changed Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q` - `12 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var\agriguard-operator-packet-absolute-command-proof --output-prefix operator-packet-absolute-command-proof --emit-handoff` - expected exit `1`; packet validation `pass`, handoff consumer `errors=[]`, artifact index `status=pass`.
- Packet `safe_rerun_commands` from `%TEMP%` - exit codes `[0, 1, 1, 1]` for env validation, guarded launch, strict preflight, and compose launch; failures stayed on `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q` - `58 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-absolute-commands.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-operator-packet-absolute-commands.json --output-dir var\agriguard-browser-smoke-suite-operator-packet-absolute-commands --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The local packet, handoff, consumer, artifact index, workspace smoke, and browser smoke paths are green around this command-copyability gap.

## Next Cycle

Audit readiness summary and launch report command surfaces for any remaining relative recovery instructions or operator-facing replay commands.
