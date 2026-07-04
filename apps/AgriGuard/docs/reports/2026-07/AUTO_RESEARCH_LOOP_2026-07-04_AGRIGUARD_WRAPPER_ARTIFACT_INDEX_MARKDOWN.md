# AutoResearch Loop 2026-07-04 AgriGuard Wrapper Artifact Index Markdown

## Objective

Have the guarded-launch wrapper emit artifact-index Markdown by default whenever it emits the artifact-index JSON, and keep downstream evidence emission running even when a post-launch evidence gate fails.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_WRAPPER_ARTIFACT_INDEX_MARKDOWN.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the wrapper can emit the artifact-index JSON, but not the paired Markdown by default; post-launch consumer failure also prevents later index emission.
- Variant: add default `*-artifact-index.md` emission and defer post-launch failure returns until handoff, consumer, and index evidence commands have all run.
- Primary KPI: live wrapper run writes artifact-index JSON and Markdown even when the env-shape-blocked path returns nonzero.
- Guardrails: no README edits, no secret values, no launch execution weakening, and fail-closed return codes are preserved.

## Variant Evidence

- Focused wrapper/index tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: `19 passed in 0.81s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `60 passed in 2.25s`
- Live wrapper refresh:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-artifact-index-markdown --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-artifact-index-markdown-status.json`
  - Expected result: exit code `1`, env-shape validation blocked, handoff validation emitted, consumer emitted, artifact-index JSON emitted, artifact-index Markdown emitted.
  - Artifact index result: `status=fail`, `consumer_packet_validation_status=fail`, `consumer_errors=["packet_validation status is not pass"]`, `missing_required_roles=[]`. This is expected for the env-shape path because no operator packet exists yet.
  - Markdown result: `var\agriguard-guarded-launch-wrapper-artifact-index-markdown-artifact-index.md` exists and shows status `fail`, consumer packet validation `fail`, missing required roles `-`, and the required `handoff_consumer_json` row.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-wrapper-artifact-index-markdown.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `563 passed, 2 warnings`.

## Decision

Adopt the variant. The one-command guarded-launch wrapper now emits both machine-readable and human-readable artifact-index evidence even when a downstream evidence gate fails closed.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Generate an operator packet for env-shape-blocked runs so packet validation can pass in wrapper evidence even before strict preflight starts.
