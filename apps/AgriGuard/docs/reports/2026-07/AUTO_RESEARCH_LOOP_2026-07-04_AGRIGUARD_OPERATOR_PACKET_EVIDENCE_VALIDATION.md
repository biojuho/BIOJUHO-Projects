# AutoResearch Loop 2026-07-04 AgriGuard Operator Packet Evidence Validation

## Objective

Add a narrow packet validation check so future guarded-launch packet changes cannot silently drop required evidence output paths.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_OPERATOR_PACKET_EVIDENCE_VALIDATION.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the operator packet lists guarded-launch evidence files, but no machine-readable check proves all required keys are still present.
- Variant: add `guarded_launch_evidence.validation` with the required output keys and explicit missing/empty key lists.
- Primary KPI: live packet render reports `EvidenceValidation=pass` while preserving the expected blocked launch state.
- Guardrails: no README edits, no secret values, no changes to upstream launch execution or external blocker classification.

## Variant Evidence

- Focused packet test:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q`
  - Result: `5 passed in 0.33s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `56 passed in 2.20s`
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-emit-index-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-evidence-validation.json --markdown-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-evidence-validation.md --env-template-out var\agriguard-guarded-launch-wrapper-emit-index-filled-evidence-validation.env.template`
  - Expected result: exit code `1`, packet `status=blocked`, `EvidenceValidation=pass`, missing keys empty, empty keys empty, artifact index path `var/agriguard-guarded-launch-artifact-index.json`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-evidence-validation.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `559 passed, 2 warnings`.

## Decision

Adopt the variant. The operator packet now carries a small self-check for the guarded-launch evidence output contract, making required evidence path regressions visible in focused tests and live packet renders.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Continue reducing launch handoff ambiguity by validating the downstream evidence consumers against the packet's guarded-launch output map.
