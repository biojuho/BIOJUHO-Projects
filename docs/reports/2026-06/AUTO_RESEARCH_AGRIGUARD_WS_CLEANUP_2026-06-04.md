# AutoResearch AgriGuard WebSocket Cleanup - 2026-06-04

## Scope

- Surface: AgriGuard cold-chain live route navigation.
- Baseline: a Python Playwright pass across Dashboard, Registry, Supply Chain, Cold-Chain, and Scanner found a browser warning: `WebSocket connection to 'ws://127.0.0.1:5174/api/ws/iot' failed: WebSocket is closed before the connection is established.`
- Variant adopted: defer closing a connecting cold-chain WebSocket until it reaches `onopen`, then close immediately. This avoids browser warning noise during fast route transitions without leaking a mounted socket handler.

## Changed Paths

- `apps/AgriGuard/frontend/src/hooks/useThrottledWebSocket.js`
- `apps/AgriGuard/frontend/src/hooks/useThrottledWebSocket.test.jsx`
- `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_WS_CLEANUP_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- existing WebSocket buffering and reconnect tests still pass,
- unmounting while the socket is still connecting does not call `close()` until `onopen`,
- live route navigation no longer reports the WebSocket close-before-established warning,
- production build and AgriGuard smoke pass.

## Evidence

- Focused tests:
  - `npm.cmd run test -- src/hooks/useThrottledWebSocket.test.jsx src/components/ColdChainMonitor.test.jsx`
  - Result: `2` test files passed, `5` tests passed.
- Live Python Playwright route pass:
  - Visited `http://127.0.0.1:5174/`, `/registry`, `/supply-chain`, `/cold-chain`, and `/scan`.
  - Screenshot: `var/agriguard-live-click-pass-ws-clean-2026-06-04.png`.
  - Result: the WebSocket console warning was removed. One request-failed event remained for `GET /api/iot/status net::ERR_ABORTED` during route navigation; no console/page error was reported.
- Frontend production build:
  - `npm.cmd run build`
  - Result: passed with Vite `8.0.16`.
- AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-ws-cleanup-2026-06-04.json`
  - Result: passed `5/5`.

## Remaining Launch Work

- Treat the remaining `/api/iot/status` navigation abort as expected route-transition cancellation unless it appears as user-visible UI failure.
- Continue managed browser passes for DeSci and Canva widget targets.
