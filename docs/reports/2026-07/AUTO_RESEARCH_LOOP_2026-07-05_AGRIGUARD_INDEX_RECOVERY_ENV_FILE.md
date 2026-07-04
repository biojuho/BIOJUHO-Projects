# AutoResearch Loop: AgriGuard Index Recovery Env File

Date: 2026-07-05

## Objective

Preserve the active guarded-launch env file in artifact-index recovery commands. A failed artifact index should tell the operator to rerun the same launch namespace with the same env file, not fall back to the default operator template.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: recovery commands must be directly replayable for the same evidence sample, including the env file and artifact namespace that produced the failure.

## A/B Contract

- Baseline: `index_guarded_launch_artifacts.py` built recovery commands with `run_guarded_launch._default_env_file(app_root)`.
- Variant: the indexer accepts `--env-file`; the guarded wrapper passes its active env file to artifact indexing.
- Primary KPI: a failed artifact-index recovery command contains the same env file used by the guarded wrapper.
- Guardrails: custom output prefix and status JSON behavior remain unchanged; strict preflight still blocks on missing Firebase; canonical smoke and browser checks remain green.
- Decision: adopt. Recovery commands now preserve the operator env-file context.

## Changed Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q` - `40 passed`.
- `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-index-recovery-env-file-proof --json-out var/agriguard-index-recovery-env-file-proof.json --markdown-out var/agriguard-index-recovery-env-file-proof.md` - expected exit `1`; status `fail`; recovery required `true`; recovery env file `D:\AI project\var\agriguard-launch-operator.missing-firebase.env`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-index-recovery-env-file.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var/agriguard-browser-smoke-suite-index-recovery-env-file.json --output-dir var/agriguard-browser-smoke-suite-index-recovery-env-file --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

Real compose/browser launch is still externally blocked until the operator provides a real outside-repo Firebase Admin service-account JSON. Recovery commands now preserve the env-file context needed to retry that exact path.

## Next Cycle

Run a full guarded handoff with a custom output directory, then inspect status, packet, handoff, index, and recovery commands for any remaining default-directory assumptions.
