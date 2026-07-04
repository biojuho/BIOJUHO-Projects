# AutoResearch Loop 2026-07-04 AgriGuard Operator Packet Guarded Wrapper Command

## Objective

Surface the full evidence-producing guarded-launch wrapper command in the launch operator packet safe rerun commands.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_OPERATOR_PACKET_GUARDED_WRAPPER_COMMAND.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the packet safe rerun command points at the guarded wrapper, but not the full handoff/consumer artifact path.
- Variant: update the packet wrapper command to include `--emit-handoff` and a status JSON output path.
- Primary KPI: live packet render exposes `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.env.template --emit-handoff --status-json-out var/agriguard-guarded-launch-status.json`.
- Guardrails: validator-first command remains first, lower-level preflight and compose commands remain available for diagnostics, and packet outputs remain redacted.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `51 passed in 1.80s`
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-emit-consumer-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-emit-consumer-filled-operator-packet-refreshed.json --markdown-out var\agriguard-guarded-launch-wrapper-emit-consumer-filled-operator-packet-refreshed.md --env-template-out var\agriguard-guarded-launch-wrapper-emit-consumer-filled-refreshed.env.template`
  - Expected result: exit code `1`, packet status `blocked`, wrapper safe rerun command includes `--emit-handoff`, action id `set_firebase_service_account_file`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-guarded-wrapper-command.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `554 passed, 2 warnings`.

## Decision

Adopt the variant. Blocked operators now see the one-command guarded launch retry that produces status, handoff, validation, and compact consumer artifacts by default.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a compact artifact index for the default guarded-launch output prefix so operators can verify every expected status, handoff, validation, consumer, packet, and env-validation artifact exists after a retry.
