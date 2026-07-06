# AutoResearch Loop - AgriGuard Artifact Freshness Gate - 2026-07-06

## Objective

Make the guarded-launch artifact index fail closed when required JSON evidence exists but lacks top-level `generated_at` freshness metadata.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_FRESHNESS_GATE_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - Defines the guarded-launch JSON artifact roles that require top-level `generated_at`.
  - Adds `missing_generated_at_roles` to the artifact index JSON.
  - Makes index `status=pass` require both no missing required artifacts and no missing freshness metadata.
  - Renders `Missing generated_at roles` in the Markdown index summary.
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - Updates complete artifact fixtures to include JSON freshness metadata.
  - Covers the pass path with `missing_generated_at_roles=[]`.
  - Adds a fail-closed regression where `handoff_consumer_json` exists but lacks `generated_at`.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - Result: `11 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: `174 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-freshness-gate.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`
  - Slowest check: `agriguard backend tests=390380ms`

## Live Artifact Index Evidence

Command:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --status-json var\agriguard-guarded-launch-status-derived-generated-at-2026-07-06.json --handoff-json var\agriguard-guarded-launch-handoff.json --handoff-markdown var\agriguard-guarded-launch-handoff.md --handoff-validation-json var\agriguard-guarded-launch-handoff.validation.json --handoff-consumer-json var\agriguard-guarded-launch-handoff.consumer.json --ready-gate-json var\agriguard-guarded-launch-ready-gate.json --json-out var\agriguard-guarded-launch-artifact-index.json --markdown-out var\agriguard-guarded-launch-artifact-index.md --exit-zero-on-fail
```

Result:

- Artifact index exit: `0`
- Artifact index JSON: `status=pass`, `blocker_class=ready`, `generated_at=2026-07-06T13:03:08Z`
- `missing_required_roles=[]`
- `missing_generated_at_roles=[]`
- Artifact rows indexed: `15`
- Markdown exposes `Missing generated_at roles: -`

## Current Launch State

The guarded-launch artifact index now fails closed on stale or incomplete freshness metadata for required JSON evidence. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
