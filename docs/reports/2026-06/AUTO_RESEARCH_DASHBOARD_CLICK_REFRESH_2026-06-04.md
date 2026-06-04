# AutoResearch Dashboard Click Refresh - 2026-06-04

## Source-Backed Candidate

- Source: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
- Source pattern: treat browser automation as a first-class dev-server workflow, not only a unit-test proxy.
- Local surface: `apps/dashboard` live operator dashboard.

## A/B Contract

- Baseline: dashboard component tests and build pass, but the live dev-server path still needs browser-click proof for the launch operator workflow.
- Variant: start the manifest-backed dashboard stack, click the visible refresh button in Chromium, verify quality/dev-server panels, capture screenshot evidence, then stop the managed stack.
- Primary KPI: live refresh click succeeds with no console errors, no page errors, no failed browser requests, and the dashboard shows `2/2 READY`.
- Guardrails: managed dev servers are stopped after proof; no source code is changed when the browser path already passes.
- Decision: adopted as evidence only. No code patch was needed.

## Verification

- `npm.cmd run build` in `apps/dashboard`
  - passed
  - Vite build produced production assets
- `npm.cmd test` in `apps/dashboard`
  - `8 passed`
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-click-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 3`
  - dashboard stack ready
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 3 --json-out var\dev-server-status-dashboard-after-start-2026-06-04.json --format table`
  - `2/2 READY`
- Chromium click proof:
  - opened `http://127.0.0.1:5173/`
  - clicked the refresh button
  - verified `AI Projects Dashboard`, `WORKSPACE SMOKE`, `DEV SERVERS`, `2/2 READY`, and visible refresh button
  - console errors: `0`
  - page errors: `0`
  - failed requests: `0`
  - screenshot: `var/dashboard-click-refresh-2026-06-04.png`
  - JSON evidence: `var/dashboard-click-refresh-2026-06-04.json`
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-dashboard-click-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies --timeout 10`
  - stopped managed stack
- `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --timeout 1 --json-out var\dev-server-status-dashboard-after-click-stop-2026-06-04.json --format table`
  - `0/2 READY` after stop

## Notes

An initial inline selector probe failed because Korean text in the temporary Python script was decoded as `???` by the shell input path. A separate browser inspection confirmed the app itself renders the expected Korean refresh aria-label and visible refresh text correctly.
