# AutoResearch AgriGuard Icon and Service Worker Fix - 2026-06-04

## Scope

- App: `apps/AgriGuard/frontend`
- Baseline: browser pass reported a missing/invalid manifest icon. Follow-up Vite dev probing also exposed stale service-worker caching of Vite dev modules, producing HMR websocket failures and React invalid-hook errors after cached dependency hashes diverged.
- Variant adopted: add the declared AgriGuard PNG icons, use the product icon as the document favicon, unregister/delete AgriGuard service-worker caches in Vite dev, and constrain production service-worker static caching to declared app-shell assets, icons, and built `/assets/` files.

## Changed Paths

- `apps/AgriGuard/frontend/public/icons/icon-192.png`
- `apps/AgriGuard/frontend/public/icons/icon-512.png`
- `apps/AgriGuard/frontend/index.html`
- `apps/AgriGuard/frontend/public/sw.js`

## Decision Rule

Adopt the variant if:

- the declared manifest icons exist and match their declared dimensions,
- frontend build still passes,
- browser navigation no longer reports manifest-icon, Vite HMR, or invalid-hook warnings after the dev service-worker cleanup runs,
- the canonical AgriGuard smoke scope passes.

## Evidence

- Icon dimensions:
  - `icon-192.png`: `192x192`
  - `icon-512.png`: `512x512`
- `npm run build` from `apps/AgriGuard/frontend`: passed.
- Browser route: `http://localhost:5173/registry?sw_cleanup=2`
  - Snapshot: `agriguard-registry-icon-sw-fixed.md`
  - Console: `agriguard-icon-sw-fixed-console.md`
  - Result: `0` errors, `0` warnings.
- Canonical smoke:
  - Command: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-icon-sw-2026-06-04.json`
  - Result: passed `5/5`.

## Remaining Launch Work

- `/supply-chain` still needs pagination or virtualization for the 500+ product dataset.
- The AgriGuard build still reports deprecated `advancedChunks` and large chunk warnings; those are separate bundle-optimization work.
- The `127.0.0.1`/`localhost` API-origin mismatch remains unless the dev runner or backend default CORS config is normalized.
