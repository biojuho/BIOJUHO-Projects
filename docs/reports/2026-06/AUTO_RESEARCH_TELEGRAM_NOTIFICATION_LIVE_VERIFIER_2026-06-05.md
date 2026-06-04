# Telegram Notification Live Verifier

## Scope

This AutoResearch cycle hardens the Telegram credential boundary. The existing
MCP service runtime smoke proves `telegram-bot` can initialize and list tools,
but it does not prove notification delivery. The goal is to add a redacted live
delivery verifier without weakening the external-credential blocker.

## A/B Decision

- Baseline: `telegram_notification_mcp_credentials` asked operators to run
  `python ops/scripts/mcp_service_runtime_smoke.py`, which validates MCP
  tools/list but does not attempt a Telegram Bot API delivery.
- Variant: add `ops/scripts/telegram_notification_live_verify.py`, a dry-run
  by default verifier that reports missing `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID`; when explicitly run with `--execute`, it calls Telegram
  Bot API `sendMessage` and writes redacted JSON/Markdown evidence.
- Primary KPI: unblock command quality for Telegram delivery improves from
  tools/list-only proof to an explicit delivery verifier.
- Guardrail: no secret values are emitted, and completion stays
  `global_objective_complete=false` until real operator credentials exist.
- Result: adopted.

## Changed Paths

- `ops/scripts/telegram_notification_live_verify.py`
- `tests/test_telegram_notification_live_verify.py`
- `ops/references/external_credential_boundaries.json`
- `docs/reports/2026-06/TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.json`
- `docs/reports/2026-06/TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.md`

## Verification

- `python ops\scripts\telegram_notification_live_verify.py --json-out docs\reports\2026-06\TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\TELEGRAM_NOTIFICATION_LIVE_VERIFY_DRY_RUN_2026-06-05.md` -> `status=pass`, `live_status=blocked_missing_required_env`, `message_sent=false`.
- `python -m pytest tests\test_telegram_notification_live_verify.py -q` -> `5 passed`.
- The external credential handoff now lists `telegram_notification_live_verify.py --execute` before the MCP service runtime smoke for the Telegram boundary.

## Remaining Boundary

The live Telegram notification is not claimed complete. It remains blocked
until the operator supplies `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then
runs:

`python ops/scripts/telegram_notification_live_verify.py --execute --json-out var/telegram-notification-live-verify.json --markdown-out var/telegram-notification-live-verify.md`

`global_objective_complete=false`
