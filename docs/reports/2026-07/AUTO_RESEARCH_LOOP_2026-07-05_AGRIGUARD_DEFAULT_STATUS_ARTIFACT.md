# AutoResearch Loop: AgriGuard Default Status Artifact

Date: 2026-07-05

## Objective

Ensure `run_guarded_launch.py --emit-handoff` writes the status JSON artifact that the operator packet advertises, even when the caller does not pass `--status-json-out`.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: durable status artifacts should exist when downstream evidence tables and artifact indexes name them as required launch evidence.

## A/B Contract

- Baseline: handoff emission without `--status-json-out` could still produce a packet whose guarded evidence outputs named a status JSON path, but the wrapper did not write that file.
- Variant: handoff runs now compute an effective default status path, pass it to packet refresh and artifact indexing, and write the compact status view during the wrapper run.
- Primary KPI: a no-`--status-json-out` guarded handoff run creates `var/<prefix>-status.json`, the packet embeds that path, and the artifact index marks `status_json` required and present.
- Guardrails: explicit custom status paths remain honored; status-only behavior is unchanged; missing Firebase still fails closed; canonical smoke and browser checks remain green.
- Decision: adopt. Handoff evidence now has a real status artifact by default.

## Changed Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `39 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch-default-status --emit-handoff` - expected exit `1`; default status exists; status `blocked`; blocker `preflight_blocked`; packet status output `var/agriguard-guarded-launch-default-status-status.json`; artifact index required `status_json=true`; missing required roles `0`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-default-status-artifact.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var/agriguard-browser-smoke-suite-default-status-artifact.json --output-dir var/agriguard-browser-smoke-suite-default-status-artifact --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. Local evidence generation is now consistent through the status JSON, packet, handoff consumer, and artifact index.

## Next Cycle

Run the guarded handoff path with both a custom output directory and custom prefix, then audit generated recovery commands for env-file preservation and exact artifact namespace reproduction.
