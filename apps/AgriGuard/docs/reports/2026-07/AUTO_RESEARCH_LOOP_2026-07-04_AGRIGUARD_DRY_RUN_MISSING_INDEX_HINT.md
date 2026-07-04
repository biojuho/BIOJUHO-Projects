# AutoResearch Loop 2026-07-04 AgriGuard Dry Run Missing Index Hint

## Objective

Mirror the missing artifact-index hint into guarded-launch dry-run output so dry-run and operator-packet surfaces both show the next wrapper command when the index is absent.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_DRY_RUN_MISSING_INDEX_HINT.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: wrapper dry-run output reports whether the selected artifact index exists, but does not provide the exact wrapper command to generate it when missing.
- Variant: add `missing_index_action` and `missing_index_command` to `artifact_index_readiness_summary`; the command preserves app root, env file, output directory, output prefix, compose/service options, browser-smoke setting, handoff emission, and status JSON path when present.
- Primary KPI: a live dry-run with a fresh prefix reports `found=false`, includes `--emit-handoff`, preserves the selected prefix, and omits `--dry-run` from the generated command.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to delegated launch or evidence gates.

## Variant Evidence

- Focused wrapper dry-run tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: `15 passed in 0.56s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `65 passed in 2.47s`
- Live dry-run check:
  - `$json = python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-dry-run-missing-index-hint --emit-handoff --dry-run | ConvertFrom-Json`
  - Result: `artifact_index_readiness_summary.found=false` and `missing_index_action=Run the guarded launch wrapper without --dry-run to generate the artifact index evidence.`
- Live command check:
  - Extracted `artifact_index_readiness_summary.missing_index_command`.
  - Result: `HasDryRun=False`, `HasEmitHandoff=True`, `Prefix=agriguard-guarded-launch-dry-run-missing-index-hint`, command head points at `apps\AgriGuard\scripts\run_guarded_launch.py`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dry-run-missing-index-hint.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `568 passed, 2 warnings`.

## Decision

Adopt the variant. Dry-run output now gives operators a runnable no-dry-run wrapper command when the selected artifact index has not yet been generated.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add the same missing-index hint to the artifact-index Markdown path for failed or partial index generation so static evidence files also name the recovery command.
