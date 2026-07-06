# AutoResearch Loop - AgriGuard Artifact Freshness Propagation - 2026-07-06

## Objective

Propagate guarded-launch artifact freshness failures from the artifact index into the status, operator-packet, handoff, and handoff-consumer surfaces operators use during launch recovery.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_FRESHNESS_PROPAGATION_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Adds `artifact_index.missing_generated_at_roles` to the compact status view.
- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - Mirrors `missing_generated_at_roles` into `guarded_launch_evidence.artifact_index_readiness_summary`.
  - Shows the field in operator-packet Markdown.
- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - Shows artifact-index freshness role gaps in handoff Markdown.
- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
  - Emits `artifact_index_missing_generated_at_roles` in the consumer JSON view.
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - Requires `status_view.artifact_index.missing_generated_at_roles`.
  - Allows optional `status_view.ready_gate.generated_at`, matching live ready-gate evidence.

## Verification

- Focused propagation/schema subset:
  - Result: `7 passed`
- Full launch/handoff suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: `175 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-freshness-propagation.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Status view:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --artifact-index-json-out var\agriguard-guarded-launch-artifact-index.json --status-only --status-json-out var\agriguard-guarded-launch-status-freshness-propagation-2026-07-06.json
```

- Result: exit `0`
- Status JSON: `status=blocked`, `blocker_class=preflight_blocked`, `generated_at=2026-07-06T13:22:43Z`
- Artifact index: `status=pass`, `blocker_class=ready`, `missing_generated_at_roles=[]`
- Preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Handoff render and validation:

```powershell
python apps\AgriGuard\scripts\render_guarded_launch_handoff.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --ready-gate-json var\agriguard-guarded-launch-ready-gate.json --json-out var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.json --markdown-out var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.md --validation-json-out var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.validation.json --exit-zero-on-blocked
```

- Result: exit `0`
- Validation: `status=pass`, `blocker_class=ready`, `errors=[]`, `generated_at=2026-07-06T13:23:46Z`

Handoff consumer:

```powershell
python apps\AgriGuard\scripts\consume_guarded_launch_handoff.py var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.json --validation-json var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.validation.json --json-out var\agriguard-guarded-launch-handoff-freshness-propagation-2026-07-06.consumer.json --exit-zero-on-blocked
```

- Result: exit `0`
- Consumer JSON: `status=fail`, `blocker_class=preflight_blocked`, `validation_status=pass`
- Artifact index: `artifact_index_status=pass`, `artifact_index_missing_generated_at_roles=[]`

## Current Launch State

Artifact freshness failures now propagate into every guarded-launch recovery surface checked in this cycle. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
