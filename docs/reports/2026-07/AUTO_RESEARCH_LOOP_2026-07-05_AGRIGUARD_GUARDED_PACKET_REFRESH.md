# AutoResearch Loop: AgriGuard Guarded Packet Refresh

Date: 2026-07-05

## Objective

Close the guarded-launch evidence gap where `var/agriguard-guarded-launch-operator-packet.json` could embed a stale `guarded_launch_evidence.artifact_index_readiness_summary` after the wrapper generated a newer artifact index. The operator packet must not contradict the final artifact index or status view.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied source-backed pattern: bounded continuous improvement with durable status artifacts and fail-closed completion audits. The local adaptation is to refresh the operator packet after artifact indexing, then rerender downstream handoff artifacts from the refreshed packet.

## A/B Contract

- Baseline: `launch_compose.py` rendered the operator packet before `run_guarded_launch.py` generated the artifact index. A later status/index pass could identify the current blocker, while the nested packet summary still reflected older readiness evidence.
- Variant: `run_guarded_launch.py` now builds an explicit `render_launch_operator_packet.py` refresh command and runs it after the first artifact-index pass, before the second handoff/consumer/artifact-index pass.
- Primary KPI: final packet summary action IDs, env readiness fields, placeholder count, and packet preflight status match the current artifact index before final handoff publication.
- Guardrails: wrapper dry-run remains inspectable, blocked launches remain fail-closed, handoff/index failures still propagate, canonical AgriGuard smoke and browser suite remain green.
- Decision: adopt. The variant removes stale nested packet evidence without weakening the external Firebase blocker.

## Changed Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` - `19 passed`.
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `17 passed`.
- `python apps/AgriGuard/scripts/validate_launch_env_template.py --env-file var/agriguard-launch-operator.missing-firebase.env --json-out var/agriguard-launch-env-template-validation-packet-refresh.json --markdown-out var/agriguard-launch-env-template-validation-packet-refresh.md` - pass, `placeholder_count=0`, `ready_for_preflight=true`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --emit-handoff --status-json-out var/agriguard-guarded-launch-status-packet-refresh-missing-firebase.json` - expected exit `1`; status `blocked`; blocker `preflight_blocked`; refreshed packet summary action IDs `set_firebase_service_account_file`; env ready `true`; placeholder count `0`; packet preflight status `fail`; artifact index action IDs `set_firebase_service_account_file`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-packet-refresh.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var/agriguard-browser-smoke-suite-packet-refresh.json --output-dir var/agriguard-browser-smoke-suite-packet-refresh --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

Real compose/browser launch is still externally blocked until an operator supplies a real Firebase Admin service-account JSON file that exists on the host and remains outside the repository. The local code path now preserves the correct blocker consistently through the operator packet, handoff, status view, and artifact index.

## Next Cycle

After a real outside-repo Firebase Admin JSON is available, rerun guarded launch with `--env-file var/agriguard-launch-operator.missing-firebase.env` updated to that host path and require the preflight to advance past `set_firebase_service_account_file` before attempting compose/browser launch proof.
