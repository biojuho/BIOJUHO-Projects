# AutoResearch Loop: AgriGuard Custom Guarded Packet Evidence

Date: 2026-07-05

## Objective

Make refreshed AgriGuard operator packets truthful for non-default guarded-launch output directories, prefixes, and status JSON paths. The previous packet refresh fixed the default prefix, but the renderer still embedded default guarded-launch evidence outputs unless it was explicitly told about the wrapper's selected artifact namespace.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: deterministic status artifacts must describe the exact run being audited, including custom artifact namespaces, not only the default launch path.

## A/B Contract

- Baseline: `render_launch_operator_packet.py` always embedded default guarded-launch evidence outputs and default artifact-index readiness lookup.
- Variant: the renderer accepts `--guarded-output-dir`, `--guarded-output-prefix`, and `--guarded-status-json`; the guarded wrapper passes those values during packet refresh.
- Primary KPI: a custom-prefix guarded launch packet embeds the same status JSON and artifact-index path as the active wrapper run.
- Guardrails: default safe rerun commands remain unchanged; custom wrappers still fail closed on missing Firebase credentials; canonical smoke and browser checks stay green.
- Decision: adopt. Custom artifact namespaces now preserve the exact evidence path through packet, handoff consumer, and artifact index.

## Changed Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `38 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch-packet-custom-prefix --emit-handoff --status-json-out var/agriguard-guarded-launch-packet-custom-prefix-status.json` - expected exit `1`; status `blocked`; blocker `preflight_blocked`; packet status output `var/agriguard-guarded-launch-packet-custom-prefix-status.json`; packet artifact-index output and readiness summary path `var/agriguard-guarded-launch-packet-custom-prefix-artifact-index.json`; action IDs `set_firebase_service_account_file`; placeholder count `0`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-custom-packet-evidence.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var/agriguard-browser-smoke-suite-custom-packet-evidence.json --output-dir var/agriguard-browser-smoke-suite-custom-packet-evidence --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The launch path is locally consistent and still correctly blocked on the external Firebase Admin service-account JSON. A real outside-repo JSON is required before compose/browser launch can advance past strict preflight.

## Next Cycle

Audit the guarded-launch operator surfaces for any remaining default-prefix assumptions in generated Markdown, recovery commands, or status-only views, then rerun the same missing-Firebase proof under a custom output directory as well as a custom prefix.
