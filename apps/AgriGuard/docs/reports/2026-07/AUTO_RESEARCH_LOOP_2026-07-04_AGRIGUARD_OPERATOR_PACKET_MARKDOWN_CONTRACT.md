# AutoResearch Loop 2026-07-04 AgriGuard Operator Packet Markdown Contract

## Objective

Add a machine-readable check that keeps the operator packet Markdown evidence table aligned with the guarded-launch evidence output map in packet JSON.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_OPERATOR_PACKET_MARKDOWN_CONTRACT.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: packet JSON validates guarded-launch evidence keys, but the human-facing Markdown table can drift from JSON without a direct check.
- Variant: parse the rendered Markdown evidence table, compare it to `guarded_launch_evidence.outputs`, and persist `markdown_table_validation` into the CLI-written packet JSON.
- Primary KPI: live packet render reports `MarkdownValidation=pass` with seven expected output keys and no missing, extra, or mismatched rows.
- Guardrails: no README edits, no secret values, no changes to launch execution, no weakening of blocked-launch status.

## Variant Evidence

- Focused packet tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q`
  - Result: `7 passed in 0.48s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `58 passed in 3.36s`
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-emit-index-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-markdown-contract.json --markdown-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-markdown-contract.md --env-template-out var\agriguard-guarded-launch-wrapper-emit-index-filled-markdown-contract.env.template`
  - Expected result: exit code `1`, packet `status=blocked`, `EvidenceValidation=pass`, `MarkdownValidation=pass`, seven expected output keys, missing rows empty, extra rows empty, path mismatches empty.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-markdown-contract.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `561 passed, 2 warnings`.

## Decision

Adopt the variant. The CLI-written operator packet now records whether the Markdown evidence table matches the JSON evidence map, so operator-facing handoff drift is visible in both tests and live packet output.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add an explicit release-handoff summary of the packet JSON validation statuses so operators can see evidence-key and Markdown-table health without opening the raw JSON.
