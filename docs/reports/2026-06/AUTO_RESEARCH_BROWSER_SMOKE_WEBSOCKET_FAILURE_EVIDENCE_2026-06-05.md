# AutoResearch: Browser Smoke WebSocket Failure Evidence

## Objective

Make direct browser-smoke evidence account for WebSocket handshake failures,
not only HTTP request failures, console errors, page errors, and expected text.

## Source Signal

- Source: `vercel/ai`
- Commit: `ce769dd2f392ec82529f626223630f8222f7b475`
- URL: `https://github.com/vercel/ai/commit/ce769dd2f392ec82529f626223630f8222f7b475`
- Relevant signal: `feat: Realtime API support for browser<->provider websocket connection`.
- Local interpretation: the upstream realtime work makes browser-to-provider
  WebSocket connection quality and secure tool-call boundaries first-class.
  Locally, browser smoke should make WebSocket failures explicit because the
  workspace has WebSocket-sensitive frontend paths and prior browser evidence
  called out WebSocket warnings.

## A/B Contract

- Baseline: `dev_server_browser_smoke.py` failed routes on HTTP status,
  missing expected text, console errors, page errors, and failed HTTP requests.
  A failed WebSocket could be hidden as a console warning or missed entirely.
- Variant: listen for Playwright `websocket` events, count observed sockets,
  record `socketerror` events, fail the route on WebSocket failure, and render
  WebSocket totals in JSON/Markdown evidence.
- Primary KPI: WebSocket handshake failures are machine-readable in browser
  smoke reports and contribute to route failure.
- Guardrails: do not change route selection, expected text matching, HTTP
  request failure handling, browser isolation, or current pass/fail status when
  WebSockets are healthy.
- Decision: adopted.

## Implementation

- `ops/scripts/dev_server_browser_smoke.py`
  - Adds `websocket_count` and `websocket_failures` to `RouteResult`.
  - Registers a Playwright `websocket` listener per route.
  - Records `socketerror` details and appends route failures as
    `websocket failed: ...`.
  - Adds summary and Markdown lines for observed WebSockets and WebSocket
    failures.
- `tests/test_dev_server_browser_smoke.py`
  - Adds a fake WebSocket regression proving a `socketerror` fails the route.
  - Updates Markdown evidence assertions to include WebSocket totals.

## Verification

- `python -m pytest tests\test_dev_server_browser_smoke.py -q`
  - `11 passed`
- `python -m py_compile ops\scripts\dev_server_browser_smoke.py`
  - passed
- `python ops\scripts\dev_server_control.py start --target canva-widget-preview --wait-ready --wait-timeout 60 --poll-interval 2 --timeout 60`
  - target already ready
- `python ops\scripts\dev_server_browser_smoke.py --target canva-widget-preview --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_WEBSOCKET_FAILURE_EVIDENCE_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_WEBSOCKET_FAILURE_EVIDENCE_2026-06-05.md`
  - status: `pass`
  - routes: `1`
  - failed: `0`
  - WebSockets observed: `1`
  - WebSocket failures: `0`
- `python ops\scripts\dev_server_control.py stop --target canva-widget-preview --timeout 20`
  - `not_managed`; the preview server was already ready before this cycle.

## Remaining Boundary

This cycle improves browser-smoke evidence for WebSocket paths. It does not
implement realtime provider connections or remove credential-gated external
runtime boundaries.

global_objective_complete=false
