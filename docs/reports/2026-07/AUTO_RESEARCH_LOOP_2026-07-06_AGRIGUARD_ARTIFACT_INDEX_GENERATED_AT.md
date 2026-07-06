# AutoResearch Loop - AgriGuard Artifact Index Generated At - 2026-07-06

## Objective

Expose per-artifact generation timestamps in the guarded-launch artifact index so an operator can audit evidence freshness from one JSON or Markdown report.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_INDEX_GENERATED_AT_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - Reads top-level `generated_at` from existing JSON artifacts when building artifact rows.
  - Adds `generated_at` to each artifact row in the index JSON.
  - Adds a `Generated` column to artifact-index Markdown.
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - Covers JSON artifact timestamp extraction.
  - Covers Markdown table exposure for per-artifact timestamps.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - Result: `10 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: `173 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `61 passed`

## Live Artifact Index Evidence

Command:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --status-json var\agriguard-guarded-launch-status-derived-generated-at-2026-07-06.json --handoff-json var\agriguard-guarded-launch-handoff.json --handoff-markdown var\agriguard-guarded-launch-handoff.md --handoff-validation-json var\agriguard-guarded-launch-handoff.validation.json --handoff-consumer-json var\agriguard-guarded-launch-handoff.consumer.json --ready-gate-json var\agriguard-guarded-launch-ready-gate.json --json-out var\agriguard-guarded-launch-artifact-index.json --markdown-out var\agriguard-guarded-launch-artifact-index.md --exit-zero-on-fail
```

Result:

- Artifact index exit: `0`
- Artifact index JSON: `status=pass`, `blocker_class=ready`, `generated_at=2026-07-06T12:57:21Z`
- `status_json`: `generated_at=2026-07-06T12:51:42Z`
- `env_validation_json`: `generated_at=2026-07-06T12:51:34Z`
- `preflight_json`: `generated_at=2026-07-06T12:51:35Z`
- `launch_report_json`: `generated_at=2026-07-06T12:51:41Z`
- `handoff_validation_json`: `generated_at=2026-07-06T12:51:41Z`
- `handoff_consumer_json`: `generated_at=2026-07-06T12:51:41Z`
- `ready_gate_json`: `generated_at=2026-07-06T12:52:04Z`
- Markdown contains the `Generated` artifact table column.

## Current Launch State

The guarded-launch artifact index now exposes freshness metadata for each timestamped JSON artifact. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
