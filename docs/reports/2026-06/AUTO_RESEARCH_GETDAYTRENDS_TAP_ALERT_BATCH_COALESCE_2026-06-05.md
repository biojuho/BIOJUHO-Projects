# AutoResearch getdaytrends TAP Alert Batch Coalesce

- Date: `2026-06-05`
- Source: `mastra-ai/mastra@3b45ea95015557a6cb9d70dc5252af54ab1b78ac`
- Source URL: `https://github.com/mastra-ai/mastra/commit/3b45ea95015557a6cb9d70dc5252af54ab1b78ac`
- Source signal: `feat(core/events): opt-in batched delivery for PubSub subscribers (#16482)`
- Local scope: `automation/getdaytrends`
- global_objective_complete=false

## Source-backed hypothesis

Mastra added opt-in PubSub batching primitives with per-subscriber policy controls and no behavior change for subscribers that do not opt in. The local TAP premium alert dispatcher already drains queued alerts in batches, but it lacked an opt-in coalescing policy for duplicate dedupe keys within one dispatch drain.

## A/B decision

- Baseline: `dispatch_tap_alert_queue()` sent every queued row returned by the batch query, so duplicate dedupe keys in the same drain could fan out repeated premium alerts.
- Variant: add `tap_alert_dispatch_coalesce=false` as an explicit opt-in. When enabled, the dispatcher keeps the first alert for each `dedupe_key`, marks later duplicates as `skipped` with `coalesced_duplicate` metadata, and sends only the retained items.
- Primary KPI: live dispatch sends fewer duplicate notifications while preserving existing default behavior.
- Guardrail: the flag defaults to `false`, so existing dispatch behavior is unchanged unless the operator opts in.
- Decision: accepted. This improves alert-delivery quality and maps directly to the Mastra opt-in batching signal.

## Evidence

- `python -m pytest automation\getdaytrends\tests\test_db.py::TestTapDealRoomFunnel::test_tap_alert_delivery_batch_and_status_update automation\getdaytrends\tests\test_tap_pipeline.py automation\getdaytrends\tests\test_config.py -q --tb=line` -> `28 passed`
- `python -m py_compile automation\getdaytrends\db_layer\tap_repository.py automation\getdaytrends\tap\service.py automation\getdaytrends\config.py automation\getdaytrends\config_env_loaders.py` -> passed
- `python ops\scripts\run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-tap-coalesce-2026-06-05.json` -> `2/2 passed`
- Coalescing path: `attempted=2`, `dispatched=2`, `skipped=1`, `coalesced=1`, duplicate alert marked `skipped`

## Follow-up

Consider surfacing `coalesced` in the dashboard TAP dispatch panel after a browser proof cycle.
