# AutoResearch Loop: AgriGuard Custom Handoff Evidence Paths

Date: 2026-07-05

## Objective

Make refreshed operator packets preserve custom guarded-launch handoff paths. The artifact index already supported custom handoff JSON, Markdown, validation, consumer, and ready-gate paths; the packet renderer now needs to advertise the same paths in its guarded evidence table and safe wrapper command.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: recovery and evidence artifacts should reproduce the exact run namespace, not silently fall back to default handoff outputs.

## A/B Contract

- Baseline: refreshed packets embedded default handoff paths even when `run_guarded_launch.py` wrote custom handoff artifacts.
- Variant: `render_launch_operator_packet.py` accepts guarded handoff output paths, and the wrapper passes its active handoff paths during packet refresh.
- Primary KPI: a custom output-directory/custom handoff run produces a packet whose guarded evidence outputs match the actual custom handoff artifacts.
- Guardrails: default packet behavior remains unchanged; custom prefix/status/env-file preservation remains intact; missing Firebase still blocks strict preflight; smoke and browser gates pass.
- Decision: adopt. Packet, handoff consumer, and artifact index now agree on custom handoff artifact paths.

## Changed Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `40 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var/agriguard-custom-handoff-output-dir --output-prefix custom-handoff-proof --handoff-json-out var/agriguard-custom-handoff-output-dir/handoff/current.handoff.json --handoff-markdown-out var/agriguard-custom-handoff-output-dir/handoff/current.handoff.md --handoff-validation-json-out var/agriguard-custom-handoff-output-dir/handoff/current.handoff.validation.json --handoff-consumer-json-out var/agriguard-custom-handoff-output-dir/handoff/current.handoff.consumer.json --handoff-ready-gate-json-out var/agriguard-custom-handoff-output-dir/handoff/current.ready-gate.json` - expected exit `1`; status `blocked`; blocker `preflight_blocked`; packet handoff outputs match the custom handoff paths; artifact index missing required roles `0`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-custom-handoff-evidence.json` - `passed=5`, `failed=0`.
- First full browser suite attempt at `var/agriguard-browser-smoke-suite-custom-handoff-evidence.json` had a transient `qr_path` navigation timeout with no console errors or request failures.
- Focused retry: `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token dev-operator-token --json-out var/agriguard-browser-smoke-suite-custom-handoff-evidence/qr-path-retry.json --screenshot-dir var/agriguard-browser-smoke-suite-custom-handoff-evidence/qr-path-retry-screens --timeout-ms 120000` - `22/22 PASS`.
- Full browser suite retry: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var/agriguard-browser-smoke-suite-custom-handoff-evidence-retry.json --output-dir var/agriguard-browser-smoke-suite-custom-handoff-evidence-retry --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The local handoff evidence path now remains consistent across custom output directory, custom handoff paths, status, packet, handoff consumer, and artifact index.

## Next Cycle

Audit the QR-path smoke script's navigation wait around `/verify/<token>` so transient navigation timeouts become more diagnosable without weakening the browser gate.
