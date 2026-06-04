# AutoResearch Canva Generic Browser Smoke - 2026-06-04

## Objective

Run the manifest-backed browser smoke runner against the Canva widget preview
and remove the browser-blocking preview defect found during the live proof.

## A/B Contract

- Baseline: `canva-widget-preview` loaded the preview route, but the browser
  smoke failed because the manifest expected title-only text and the widgets
  requested remote Canva marketplace thumbnails that Chromium blocked.
- Variant: use deterministic inline SVG thumbnails in the preview/mock widget
  data, remove dead remote preview constants, and assert visible page text in
  the shared browser-smoke manifest.
- Primary KPI: `dev_server_browser_smoke.py --target canva-widget-preview`
  passes with no console, page, or request failures.
- Guardrails: Canva typecheck/build stay green, focused browser/audit tests
  remain green, and the managed preview process is stopped after proof.

## Verification

- `npm ci` in `mcp\canva-mcp`
  - Result: installed local preview dependencies; npm reported `4` moderate
    audit findings that were not changed in this browser-smoke slice.
- `cmd /c npm run typecheck` in `mcp\canva-mcp`
  - Result: pass.
- `python ops\scripts\dev_server_browser_smoke.py --validate-only --target canva-widget-preview --json-out var\dev-server-browser-smoke-canva-validate-2026-06-04.json`
  - Result: status `valid`, `1` configured route, `0` failures.
- `python ops\scripts\dev_server_browser_smoke.py --target canva-widget-preview --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.md`
  - Result: pass, `1/1` route, `0` failures.
- `cmd /c npm run build` in `mcp\canva-mcp`
  - Result: pass; generated widget assets refreshed.
- `python -m pytest tests\test_dev_server_browser_smoke.py tests\test_autoresearch_completion_audit.py`
  - Result: `8 passed`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-completion-audit-canva-browser-smoke-2026-06-04.json`
  - Result: valid, `cycle_evidence_ready=true`,
    `global_objective_complete=false`.
- `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-canva-generic-browser-stop-2026-06-04.json stop --target canva-widget-preview --timeout 10`
  - Result: stopped.
- `python ops\scripts\dev_server_status.py --target canva-widget-preview --format table`
  - Result after stop: `UNREADY`, `timed out`.

## Decision

Adopted. Canva widget preview now has committed generic browser-smoke evidence
under the shared manifest-backed runner, and its local preview no longer relies
on remote thumbnail hosts for the smoke path.
