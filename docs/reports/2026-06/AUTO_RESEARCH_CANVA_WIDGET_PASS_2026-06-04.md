# AutoResearch Canva MCP Widget Pass - 2026-06-04

## Scope

- App: `mcp/canva-mcp`
- Surface: local widget preview plus stdio/OAuth readiness checks.
- Preview URL: `http://127.0.0.1:5173/src/dev/preview.html`
- Method: npm regression commands, Canva doctor, Playwright navigation/click pass.

## Verification

- `npm run test:local`
  - Build completed.
  - `scripts/canva-auth-smoke.mjs` syntax check passed.
  - `scripts/canva-doctor.mjs` syntax check passed.
  - Node test runner passed `4/4` stdio/OAuth regression tests.
- `npm run doctor:canva`
  - Credentials configured.
  - Redirect URI: `http://localhost:8001/auth/callback`.
  - `dist/server/stdio.js` built.
  - `TOKEN_STORE=file`.
  - `canva-local` registered and enabled.
  - MCP stdio exposed `22` tools.
  - OAuth callback was listening after clearing stale `dist/server/stdio.js` listener on port `8001`.
  - Live Canva OAuth remains unauthenticated.
- Playwright preview pass:
  - Loaded generator, search, and editor widgets.
  - Clicked theme toggle.
  - Selected a generated candidate.
  - Activated a search result card.
  - Switched the editor to page tab `2`.
  - Post-fix console evidence: `0` errors and `0` warnings.

## Change

Added a source-level SVG favicon and linked it from the Canva preview/component HTML entrypoints. This removed the browser `favicon.ico` 404 that appeared on first preview load.

Changed source files:

- `mcp/canva-mcp/public/favicon.svg`
- `mcp/canva-mcp/src/dev/preview.html`
- `mcp/canva-mcp/src/components/canva-design-editor.html`
- `mcp/canva-mcp/src/components/canva-design-generator.html`
- `mcp/canva-mcp/src/components/canva-search-designs.html`

Local evidence:

- `canva-preview-loaded.md`
- `canva-preview-post-click.md`
- `canva-preview-favicon-fixed-loaded.md`
- `canva-preview-favicon-fixed-post-click.md`
- `canva-preview-favicon-fixed-console.md`

## Remaining Blocker

The local stdio/runtime path is healthy, but live Canva OAuth is still not authenticated. The next live check is `npm run auth:canva -- --query smoke-test` after confirming the Canva Developer app redirect URI exactly matches `http://localhost:8001/auth/callback`.
