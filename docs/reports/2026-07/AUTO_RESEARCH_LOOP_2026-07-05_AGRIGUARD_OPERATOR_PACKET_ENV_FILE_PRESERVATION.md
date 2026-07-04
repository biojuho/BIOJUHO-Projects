# AutoResearch Loop - AgriGuard Operator Packet Env File Preservation

Date: 2026-07-05

## Objective

Keep AgriGuard launch failure handoffs faithful to the operator command that
created them. When `launch_compose.py --env-file ...` fails before compose
startup, the generated operator packet must preserve that env-file path in safe
rerun commands instead of falling back to commands that omit the file.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_OPERATOR_PACKET_ENV_FILE_PRESERVATION.md`

## External Sources Checked

- Docker Compose variable interpolation documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/`
- Docker Compose environment-variable precedence documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/`
- Veritas AutoResearch source:
  `https://github.com/Veritas-7/autoresearch-skill-system`
  - Latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

Baseline: operator packets had generic safe rerun commands. Even when
`launch_compose.py` was invoked with a concrete `--env-file`, the packet told
operators to rerun validation, guarded launch, preflight, and compose without
that file or with the generated template path.

Variant: pass the launcher env-file list into `render_launch_operator_packet.py`
and render safe rerun commands with those same env-file paths. For the guarded
launch wrapper and shape validation, preserve the exact single env file when one
was supplied; preserve all env files for strict preflight and compose reruns.

Primary KPI: a real blocked launch handoff records the env file under
`operator_env_files` and every safe rerun command retains that file.

Decision rule: adopt only if unit coverage, a real blocked launch handoff,
canonical AgriGuard smoke, and browser click smoke all pass.

## Adopted Variant

Adopted. `render_launch_operator_packet.py` now accepts repeated `--env-file`
arguments, records redacted path-only `operator_env_files`, and builds
env-file-aware safe rerun commands. `launch_compose.py` forwards its resolved
env-file list into packet generation for dry-run planning and failure handoff.

The packet still redacts secret values. It records only file paths and does not
serialize environment values.

## Verification

- `python -m ruff check apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/launch_compose.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py -q`
  - Result: `28 passed`
- Real blocked handoff:
  - Command used `launch_compose.py --env-file var\agriguard-launch-operator-missing-firebase-env-file-preservation.env ... --service backend`
  - Result: expected exit code `1`
  - Launch report: preflight failed; compose was not run
  - Operator packet: `status=blocked`, `preflight_status=fail`
  - Readiness summary: `status=blocked`, `blocker_class=preflight_blocked`
  - Operator action IDs: `set_firebase_service_account_file`, `fix_docker_readiness`
  - `operator_env_files`: `var/agriguard-launch-operator-missing-firebase-env-file-preservation.env`
  - Safe rerun commands preserved that env file in validation, guarded launch,
    strict preflight, and compose retry commands
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-env-file-preservation.json`
  - Result: `passed=5, failed=0`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-operator-packet-env-file-preservation.json --output-dir var\agriguard-browser-smoke-suite-operator-packet-env-file-preservation --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshots_passed=18`

## Commit And Push Status

This report is part of the implementation commit for the cycle:
`Preserve AgriGuard launch env files in operator packets`.

Push target: `origin feat/shared-llm-modernization-2026-06-19`.

## Remaining Blocker

AgriGuard launch is still intentionally blocked until a real Firebase Admin
service-account JSON is provided from outside the repository. This cycle
improves the blocked-state operator handoff; it does not fabricate or replace
that external credential.

## Next Cycle

After the real Firebase credential path is available, use the guarded launch
wrapper with the operator env file, then require the packet/readiness artifacts,
compose startup, and browser smoke to all pass before clearing launch readiness.
