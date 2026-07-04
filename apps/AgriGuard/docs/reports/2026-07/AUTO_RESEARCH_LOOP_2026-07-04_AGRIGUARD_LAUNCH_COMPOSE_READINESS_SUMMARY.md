# AutoResearch Loop 2026-07-04 AgriGuard Launch Compose Readiness Summary

## Objective

Let `launch_compose.py` optionally emit a compact launch-readiness summary after any failed launch stage, so the launch report carries both the failing stage and the current blocker classification.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_LAUNCH_COMPOSE_READINESS_SUMMARY.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: `launch_compose.py` writes the stage report and, on preflight failure, an operator packet, but a separate summarizer command is needed to classify the blocker.
- Variant: add `--readiness-summary-json` and `--readiness-summary-markdown`; failed stages write the launch report, run the readiness summarizer with `--exit-zero-on-blocked`, then attach the summary child report.
- Primary KPI: guarded placeholder launches attach `env_shape_blocked`, and shape-safe fake-Firebase launches attach `preflight_blocked`.
- Guardrails: no env values in summary output, stale summary JSON is cleared before summarizer execution, compose still does not run after failed validation/preflight, and canonical AgriGuard smoke remains green.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `21 passed in 1.06s`
- Placeholder guarded launch with summary:
  - `python apps/AgriGuard/scripts/launch_compose.py --env-file var\agriguard-launch-operator.env.template --validate-env-file-shape --env-validation-json-out var\agriguard-launch-compose-summary-placeholder-validation.json --env-validation-markdown-out var\agriguard-launch-compose-summary-placeholder-validation.md --json-out var\agriguard-launch-compose-summary-placeholder-preflight.json --launch-report-json var\agriguard-compose-launch-summary-placeholder-report.json --readiness-summary-json var\agriguard-launch-compose-summary-placeholder-readiness.json --readiness-summary-markdown var\agriguard-launch-compose-summary-placeholder-readiness.md --run-browser-smoke`
  - Expected result: exit code `1`, `stage=env_shape_validation`, `stop_reason=env_shape_validation_failed`, results `env_validation,readiness_summary`, attached `blocker_class=env_shape_blocked`.
- Shape-safe fake-Firebase guarded launch with summary:
  - `python apps/AgriGuard/scripts/launch_compose.py --env-file var\agriguard-launch-shape-validation-filled.env --validate-env-file-shape --env-validation-json-out var\agriguard-launch-compose-summary-filled-validation.json --env-validation-markdown-out var\agriguard-launch-compose-summary-filled-validation.md --json-out var\agriguard-launch-compose-summary-filled-preflight.json --launch-report-json var\agriguard-compose-launch-summary-filled-report.json --operator-packet-json var\agriguard-launch-compose-summary-filled-packet.json --operator-packet-markdown var\agriguard-launch-compose-summary-filled-packet.md --operator-env-template var\agriguard-launch-compose-summary-filled.env.template --readiness-summary-json var\agriguard-launch-compose-summary-filled-readiness.json --readiness-summary-markdown var\agriguard-launch-compose-summary-filled-readiness.md --run-browser-smoke`
  - Expected result: exit code `1`, `stage=preflight`, `stop_reason=preflight_failed`, results `env_validation,preflight,operator_packet,readiness_summary`, attached `blocker_class=preflight_blocked`, operator action id `set_firebase_service_account_file`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-compose-readiness-summary.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `529 passed, 2 warnings`.

## Decision

Adopt the variant. A failed guarded launch can now produce the operator packet and the compact readiness summary in the same execution, with the summary also embedded in the launch report's `child_reports`.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a short operator-facing wrapper command or documented make-style alias that runs the guarded launch with env validation and readiness-summary output paths consistently.
