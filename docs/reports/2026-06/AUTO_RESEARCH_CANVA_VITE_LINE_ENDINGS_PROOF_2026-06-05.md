# AutoResearch: Canva Vite Line Endings Proof

## Objective

Refresh the browser/product proof after remote commit `06feb55` changed
`mcp/canva-mcp/vite.config.ts` to normalize generated HTML line endings.

## A/B Contract

- Baseline: current-tip and protected-path freshness were pinned to proof
  commit `9c86c89`.
- Variant: accept the upstream Canva Vite plugin change only after proving the
  Canva widget still builds, renders, and responds to direct click/keyboard
  smoke checks.
- Primary KPI: Canva widget preview remains browser-smoke clean after the Vite
  config change.
- Guardrails: production build passes, generic route smoke passes, click and
  keyboard widget actions remain `8/8`, and the managed preview server stops.
- Decision: adopted. The protected-path proof baseline is refreshed to
  `06feb55`.

## Verification

- `cmd /c "cd mcp\canva-mcp && npm run build"`
  - passed
  - Vite built the widget HTML, CSS, and JS assets successfully.
- `python ops\scripts\dev_server_control.py start --target canva-widget-preview --wait-ready --wait-timeout 60 --poll-interval 2 --timeout 60`
  - ready: `canva-widget-preview`
- `python ops\scripts\dev_server_browser_smoke.py --target canva-widget-preview --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_VITE_LINE_ENDINGS_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_VITE_LINE_ENDINGS_2026-06-05.md`
  - `pass`
  - `1/1` routes
  - `failed=0`
- `python ops\scripts\canva_widget_click_smoke.py --json-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_VITE_LINE_ENDINGS_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_VITE_LINE_ENDINGS_2026-06-05.md`
  - `pass`
  - `8/8` actions
  - `failed=0`
- `python ops\scripts\dev_server_control.py stop --target canva-widget-preview --timeout 20`
  - stopped

## Freshness Update

- `current_tip_freshness_gate` baseline: `06feb55`
- `protected_path_freshness` baseline: `06feb55`
- Changed protected path covered by this proof:
  `mcp/canva-mcp/vite.config.ts`

## Remaining Boundary

This proof covers the local Canva widget build and browser path. It does not
provide Canva OAuth credentials or live OpenAPI tool execution; those remain
operator-owned external credential boundaries, so
`global_objective_complete=false`.
