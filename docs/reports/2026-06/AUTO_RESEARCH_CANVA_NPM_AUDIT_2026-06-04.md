# AutoResearch Canva NPM Audit - 2026-06-04

## Objective

Resolve the moderate npm audit findings observed while preparing the Canva
widget preview browser-smoke proof.

## A/B Contract

- Baseline: `npm audit --json` in `mcp\canva-mcp` reported `4` moderate
  vulnerabilities: direct `wrangler`, transitive `miniflare`, transitive `ws`,
  and transitive `qs`.
- Variant: update the direct Cloudflare dev tool to `wrangler@^4.98.0` and
  refresh the transitive `qs` lock entry to the patched `6.15.2` release.
- Primary KPI: `npm audit --json` reports `0` vulnerabilities.
- Guardrails: Canva build still passes, dependency tree resolves to patched
  `miniflare`, `ws`, and `qs` versions, and package changes stay limited to
  package metadata plus audit evidence.

## Verification

- `cmd /c npm view wrangler version`
  - Result: `4.98.0`.
- `cmd /c npm view qs version`
  - Result: `6.15.2`.
- `cmd /c npm install --save-dev wrangler@^4.98.0`
  - Result: updated Wrangler side; audit dropped to `1` moderate finding.
- `cmd /c npm update qs`
  - Result: updated transitive `qs`; npm reported `found 0 vulnerabilities`.
- `cmd /c npm ls wrangler miniflare ws qs`
  - Result: `wrangler@4.98.0`, `miniflare@4.20260603.0`, `ws@8.20.1`,
    `qs@6.15.2`.
- `cmd /c npm audit --json > ..\..\docs\reports\2026-06\CANVA_NPM_AUDIT_2026-06-04.json`
  - Result: JSON evidence reports `total: 0` vulnerabilities.
- `cmd /c npm run build`
  - Result: pass.
- `git diff --check`
  - Result: pass after normalizing generated HTML line endings.

## Decision

Adopted. Canva MCP dev dependencies no longer carry the four moderate npm
audit findings, and the package build remains green.
