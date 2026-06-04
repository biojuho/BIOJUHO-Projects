# Canva Widget Accessible Click Smoke

- Date: 2026-06-05
- Scope: `mcp/canva-mcp` widget preview controls and cards
- Baseline: Canva widget preview had mouse-clickable carousel/search cards, but the cards were not focusable command controls and direct click evidence only covered route/text readiness.
- Variant: add accessible labels, `role="button"`, keyboard focus, Enter/Space activation, and a reusable click smoke for the widget preview.
- Primary KPI: direct widget interaction proof across mouse and keyboard actions.
- Guardrails: no console/page/request failures; postMessage events still emit the expected Canva widget actions; TypeScript typecheck and production build remain green.

## Source-Backed Rule

- W3C WAI-ARIA APG Button Pattern: button-like controls should activate with `Space` and `Enter`. Source: https://www.w3.org/WAI/ARIA/apg/patterns/button/
- MDN ARIA button role: non-native button elements need focusability plus keyboard handling, not just `role="button"`. Source: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/button_role

## Adopted Variant

Adopted. The Canva widget preview now exposes accessible labels for carousel scroll controls, candidate cards, and search result cards. Candidate/search cards support click, `Enter`, and `Space`, and the selected candidate checkmark is positioned relative to the selected card.

## Changed Paths

- `mcp/canva-mcp/src/components/canva-design-generator.tsx`
- `mcp/canva-mcp/src/components/canva-search-designs.tsx`
- `mcp/canva-mcp/src/dev/preview.tsx`
- `mcp/canva-mcp/assets/`
- `ops/scripts/canva_widget_click_smoke.py`
- `tests/test_canva_widget_click_smoke.py`

## Evidence Artifacts

- `docs/reports/2026-06/CANVA_WIDGET_CLICK_SMOKE_ACCESSIBLE_CONTROLS_2026-06-05.md`
- `docs/reports/2026-06/CANVA_WIDGET_CLICK_SMOKE_ACCESSIBLE_CONTROLS_2026-06-05.json`

## Verification

- `python -m pytest tests\test_canva_widget_click_smoke.py -q` -> `4 passed`
- `python -m py_compile ops\scripts\canva_widget_click_smoke.py tests\test_canva_widget_click_smoke.py` -> pass
- `cmd /c "cd mcp\canva-mcp && npm run typecheck"` -> pass
- `cmd /c "cd mcp\canva-mcp && npm run build"` -> pass
- `python ops\scripts\dev_server_control.py start --target canva-widget-preview --wait-ready --wait-timeout 60 --timeout 60` -> ready
- `python ops\scripts\canva_widget_click_smoke.py --json-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_ACCESSIBLE_CONTROLS_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_ACCESSIBLE_CONTROLS_2026-06-05.md` -> `pass: 8/8 actions, failed=0`

## Remaining Boundary

This improves and verifies local Canva widget interaction. Live Canva OAuth/OpenAPI execution still requires operator-provided credentials and consent.

global_objective_complete=false
