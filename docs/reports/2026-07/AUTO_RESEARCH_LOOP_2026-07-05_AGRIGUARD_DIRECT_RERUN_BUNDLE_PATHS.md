# AutoResearch Loop: AgriGuard Direct Rerun Bundle Paths

## Objective

Harden the AgriGuard launch operator packet so every readiness rerun command reproduces the active guarded artifact bundle instead of falling back to default `var/agriguard-*` output paths.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_prepare_launch_env.py`

The last two test files only defang fake Firebase private-key delimiters so the repo-wide secret-pattern contract can pass without changing runtime behavior.

## External Sources Checked

- Veritas AutoResearch source: `Veritas-7/autoresearch-skill-system`, observed `main` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, regenerated successfully with 8 sources and 8 adopted patterns.

## A/B Hypothesis

- Baseline: guarded launch packets preserved the guarded wrapper command, but direct `validate_env_template`, `strict_preflight`, and `compose_launch` commands still emitted default output paths.
- Variant: pass explicit env-validation, preflight, launch-report, operator-packet, env-template, readiness-summary, and guarded metadata paths through the operator packet renderer and guarded refresh command.
- Primary KPI: generated handoff consumer exposes 4 readiness commands, all `shell=powershell`, all pointing at the active guarded prefix.
- Decision rule: adopt only if the real guarded wrapper still blocks fail-closed on the known missing Firebase Admin service account, packet/handoff validation remains clean, focused tests pass, and workspace/app/browser smoke pass.

## Variant Evidence

Real guarded wrapper command:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-direct-rerun-bundle-paths --emit-handoff --status-json-out var\agriguard-direct-rerun-bundle-paths-status.json
```

Expected result: exit `1` because `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Generated consumer proof:

```json
{"command_count":4,"names":"validate_env_template,guarded_launch,strict_preflight,compose_launch","shells":"powershell","bundle_path_hits":4,"compose_has_bundle_outputs":true}
```

The direct `compose_launch` command now carries `--env-validation-json-out`, `--env-validation-markdown-out`, `--json-out`, `--launch-report-json`, `--operator-packet-json`, `--operator-packet-markdown`, `--operator-env-template`, `--readiness-summary-json`, `--readiness-summary-markdown`, and the guarded output prefix/status/handoff paths for `agriguard-direct-rerun-bundle-paths`.

## Verification Commands

- `python -m py_compile apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py`
- `python -m ruff check apps/AgriGuard/scripts/render_launch_operator_packet.py apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` -> 53 passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q` -> 80 passed.
- `python -m pytest tests/test_security_gate_contracts.py -q` -> 15 passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q` -> 72 passed.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-agriguard-direct-rerun-bundle-paths-rerun.json` -> 9 passed, 0 failed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-direct-rerun-bundle-paths.json` -> 5 passed, 0 failed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-direct-rerun-bundle-paths-rerun.json --output-dir var\agriguard-browser-smoke-direct-rerun-bundle-paths-rerun --timeout-ms 120000` -> 6 flows, 135 checks, 18 screenshot artifacts passed.

## Adopt Decision

Adopted. The variant improves operator reproducibility and evidence locality without changing the external launch blocker classification. Launch remains fail-closed until an operator supplies a real Firebase Admin service-account JSON outside the repo.

## Commit And Push Status

Pending at report creation.

## Next Cycle

Audit the launch operator packet and artifact index for any remaining default-path command surfaces outside `readiness_next_commands`, especially recovery commands embedded in secondary summaries.
