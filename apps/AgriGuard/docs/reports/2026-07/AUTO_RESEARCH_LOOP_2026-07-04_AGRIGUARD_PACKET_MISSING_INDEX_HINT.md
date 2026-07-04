# AutoResearch Loop 2026-07-04 AgriGuard Packet Missing Index Hint

## Objective

Add an explicit operator hint when the packet readiness summary cannot find the canonical guarded-launch artifact index.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_PACKET_MISSING_INDEX_HINT.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the packet readiness summary reports `found=false` for a missing canonical artifact index, but does not state the exact safe command that generates it.
- Variant: add `missing_index_action` and `missing_index_command` to the summary and render both fields in packet Markdown.
- Primary KPI: live packet JSON and Markdown point at the guarded wrapper command when the artifact index is missing.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to packet failure semantics.

## Variant Evidence

- Focused operator packet tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q`
  - Result: `10 passed in 0.75s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `64 passed in 3.29s`
- Live packet render:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-missing-preflight-for-index-readiness.json --json-out var\agriguard-operator-packet-missing-index-hint.json --markdown-out var\agriguard-operator-packet-missing-index-hint.md --exit-zero-on-blocked`
  - Result: exit code `0`, readiness summary reports `found=false`, `missing_index_action=Run the guarded launch wrapper command to generate the artifact index evidence.`, and `missing_index_command=python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.env.template --emit-handoff --status-json-out var/agriguard-guarded-launch-status.json`.
- Live Markdown check:
  - `Select-String -Path var\agriguard-operator-packet-missing-index-hint.md -Pattern 'Missing index action|Missing index command'`
  - Result: Markdown includes both the missing-index action and the guarded wrapper command.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-packet-missing-index-hint.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `567 passed, 2 warnings`.

## Decision

Adopt the variant. Operator packets now tell the operator how to generate the canonical artifact index when the readiness summary is missing.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Mirror the missing-index hint into wrapper dry-run output so both packet and dry-run surfaces carry the same next command when the artifact index is absent.
