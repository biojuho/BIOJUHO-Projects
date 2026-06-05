# AutoResearch: Canva Widget Message Capture Order Guard

## Objective

Make Canva widget click-smoke evidence preserve browser capture order even when
the widget payload carries message-level or part-level timestamps.

## Source Signal

- Source: `mastra-ai/mastra`
- Commit: `0c72f032abb13254df5a7856d64be2f207b8006d`
- URL: `https://github.com/mastra-ai/mastra/commit/0c72f032abb13254df5a7856d64be2f207b8006d`
- Relevant signal: `fix(core): keep part timestamps out of message ordering (#17598)`.

## A/B Contract

- Baseline: `canva_widget_click_smoke.py` captured `postMessage` payloads as
  raw objects. The array order was currently preserved, but the report had no
  explicit ordering field, so a future formatter or consumer could sort by a
  nested payload timestamp and make evidence disagree with the actual browser
  event sequence.
- Variant: stamp each captured browser message with a monotonic
  `capture_index`, normalize legacy captures with sequential indexes, and keep
  Markdown output tied to that capture order.
- Primary KPI: click-smoke reports expose deterministic event order for every
  captured Canva widget message.
- Guardrails: do not change widget `postMessage` behavior, do not sort captured
  messages, and preserve payload timestamps as metadata.
- Decision: adopted.

## Implementation

- `ops/scripts/canva_widget_click_smoke.py`
  - Initializes `window.__canvaClickMessageSequence`.
  - Adds `capture_index` at browser-message capture time.
  - Normalizes captured messages without reordering them.
  - Shows the capture index in Markdown message evidence.
- `tests/test_canva_widget_click_smoke.py`
  - Locks the new report field.
  - Adds a regression test where a first captured message has a later nested
    part timestamp than the next message, and proves the report keeps capture
    order `[0, 1]`.

## Verification

- `python -m pytest tests\test_canva_widget_click_smoke.py -q`
  - `5 passed`
- `python -m py_compile ops\scripts\canva_widget_click_smoke.py`
  - passed
- `python ops\scripts\canva_widget_click_smoke.py --json-out var\canva-widget-click-smoke-message-order.json --markdown-out var\canva-widget-click-smoke-message-order.md`
  - pass: `8/8` actions
  - messages: `4`
  - capture order: `0`, `1`, `2`, `3`

## Remaining Boundary

This cycle hardens Canva browser-click evidence. It does not claim the open-ended
AutoResearch objective complete; external credential and runtime boundaries still
remain operator-owned.

global_objective_complete=false
