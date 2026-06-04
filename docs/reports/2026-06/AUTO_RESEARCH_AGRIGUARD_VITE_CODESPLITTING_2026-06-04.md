# AutoResearch AgriGuard Vite Code Splitting - 2026-06-04

## Scope

- App: `apps/AgriGuard/frontend`
- Surface: production build configuration
- Baseline: `npm run build` completed, but reported a deprecated `advancedChunks` option, an `esbuild`/`oxc` option conflict, and JavaScript chunks over the configured `200 kB` warning limit.
- Variant adopted: migrate the production split config to Rolldown `codeSplitting`, remove the conflicting Vite `esbuild.drop` setting, and split large vendor surfaces into smaller deterministic groups.

## External Sources Checked

- Vite migration guide: `https://vite.dev/guide/migration.html`
- Rolldown `OutputOptions.codeSplitting`: `https://rolldown.rs/reference/outputoptions.codesplitting`
- Oxc minifier dead-code elimination/drop options: `https://oxc.rs/docs/guide/usage/minifier/dead-code-elimination`

## Changed Paths

- `apps/AgriGuard/frontend/vite.config.js`

## Decision Rule

Adopt the variant if:

- the deprecated `advancedChunks` warning disappears,
- the `esbuild`/`oxc` conflict warning disappears,
- no emitted JavaScript chunk exceeds the configured `200 kB` warning limit,
- the frontend production build succeeds,
- the canonical AgriGuard smoke scope passes.

## Evidence

- Frontend build:
  - `npm run build`
  - Result: passed.
  - Warning status: no deprecated `advancedChunks` warning, no `esbuild`/`oxc` conflict warning, and no chunk-size warning.
  - Largest emitted JavaScript chunk: `dist/assets/vendor-react-dom-CaBphQB0.js`, `177.77 kB`, under the configured `200 kB` warning limit.
- Canonical smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-vite-codesplitting-2026-06-04.json`
  - Result: passed `5/5`.
  - Frontend build command inside smoke: `npm.cmd run build:lts`.
  - Largest emitted JavaScript chunk inside smoke: `dist/assets/vendor-react-dom-CaBphQB0.js`, `177.77 kB`, under the configured `200 kB` warning limit.

## Remaining Launch Work

- Consider a follow-up route-level lazy-loading pass if future UI additions push `QRReader` or React vendor chunks back toward the warning limit.
