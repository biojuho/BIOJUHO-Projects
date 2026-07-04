# AutoResearch Loop 2026-07-04 AgriGuard Operator Packet Evidence Outputs

## Objective

Add an operator-packet evidence-output section that lists the default files produced by the full guarded-launch wrapper command, including the artifact index.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_OPERATOR_PACKET_EVIDENCE_OUTPUTS.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the operator packet includes the one-command guarded wrapper, but does not list the default evidence files it writes.
- Variant: add `guarded_launch_evidence.outputs` to the packet JSON and a Markdown table for status, launch report, handoff, validation, consumer, and artifact-index files.
- Primary KPI: live packet render lists `var/agriguard-guarded-launch-artifact-index.json` and preserves the full wrapper command with `--emit-handoff`.
- Guardrails: no README edits, no secret values, validator-first command order preserved.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `56 passed in 2.51s`
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-emit-index-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-evidence-outputs.json --markdown-out var\agriguard-guarded-launch-wrapper-emit-index-filled-operator-packet-evidence-outputs.md --env-template-out var\agriguard-guarded-launch-wrapper-emit-index-filled-evidence-outputs.env.template`
  - Expected result: exit code `1`, packet `status=blocked`, `guarded_launch_evidence.outputs.artifact_index_json=var/agriguard-guarded-launch-artifact-index.json`, wrapper command includes `--emit-handoff`, action id `set_firebase_service_account_file`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-evidence-outputs.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `559 passed, 2 warnings`.

## Decision

Adopt the variant. The operator packet now tells blocked operators both which one-command retry to run and which evidence files to inspect afterward.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a narrow validation check for the packet's guarded-launch evidence output map so future packet changes cannot silently drop required evidence paths.
