# AutoResearch Loop 2026-07-04 AgriGuard Operator Packet Index Contract

## Objective

Align the operator packet's guarded-launch evidence output map with the downstream artifact index contract so required launch evidence paths stay single-sourced.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_OPERATOR_PACKET_INDEX_CONTRACT.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the packet validates required evidence output keys, but the required list and paths are still local to the packet renderer.
- Variant: expose the artifact index's required core roles, have the packet validation consume that contract, and derive output paths through the artifact index path resolver.
- Primary KPI: live packet render reports `EvidenceValidation=pass` with `handoff_markdown` included in required evidence outputs.
- Guardrails: no README edits, no secret values, no launch execution changes, no weakening of blocked-launch classification.

## Variant Evidence

- Focused packet/index tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: `9 passed in 0.59s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `56 passed in 2.34s`
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-emit-index-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-index-contract.json --markdown-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-index-contract.md --env-template-out var\agriguard-guarded-launch-wrapper-emit-index-filled-index-contract.env.template`
  - Expected result: exit code `1`, packet `status=blocked`, `EvidenceValidation=pass`, missing keys empty, empty keys empty, required keys include `handoff_markdown`, and `handoff_markdown=var/agriguard-guarded-launch-handoff.md`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-index-contract.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `559 passed, 2 warnings`.

## Decision

Adopt the variant. The packet evidence map now follows the artifact index's required-role contract and path resolver, so the operator packet and downstream launch evidence consumer fail or pass against the same evidence set.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a machine-readable contract check for the operator packet Markdown evidence table so the human handoff cannot drift from the JSON packet.
