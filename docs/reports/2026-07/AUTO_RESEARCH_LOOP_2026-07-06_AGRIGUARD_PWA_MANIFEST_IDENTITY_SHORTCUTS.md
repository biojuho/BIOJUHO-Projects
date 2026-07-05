# AutoResearch Loop - AgriGuard PWA Manifest Identity And Shortcuts

Date: 2026-07-06

## Source basis

- AutoResearch/Karpathy source guard refreshed against `https://github.com/Veritas-7/autoresearch-skill-system.git` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- MDN's manifest documentation source on GitHub describes a web app manifest as app metadata used by browsers for PWA install presentation, including name and icons: https://github.com/mdn/content/blob/main/files/en-us/web/progressive_web_apps/manifest/index.md
- The W3C Web Application Manifest spec defines `start_url`, `id`, `scope`, and `shortcuts` members: https://www.w3.org/TR/appmanifest/

## Baseline finding

The existing AgriGuard PWA manifest had the install basics (`name`, `short_name`, icons, `start_url`, display, theme colors), but there was no test gate for:

- stable app identity through `id`
- explicit navigation scope through `scope`
- installed-app shortcuts for the public mobile workflows
- install metadata remaining linked from `index.html`

Failing-first evidence:

- `npm run test -- pwaMetadata.test.js`: failed because `manifest.id` was `undefined` and `manifest.shortcuts` was absent.

## Adopted changes

- Added `id: "/"` and `scope: "/"` to `public/manifest.json`.
- Added two in-scope installed-app shortcuts:
  - `/scan` for QR scanning
  - `/supply-chain` for tracked harvest batch review
- Added `src/pwaMetadata.test.js` to gate install metadata, maskable 192/512 icons, HTML manifest/theme linkage, replacement-character regressions, and shortcut URLs that correspond to existing React routes.

## Evidence

- `npm run test -- pwaMetadata.test.js`: 1 file passed, 2 tests.
- `npm run test -- pwaMetadata.test.js serviceWorkerPolicy.test.js`: 2 files passed, 4 tests.
- `npm run build:lts`: passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`: passed=5, failed=0, total=5.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-pwa-manifest-2026-07-06.json`: status `blocked`, blocker_class `preflight_blocked`.

## Remaining blocker

Launch remains externally blocked on operator-provided Firebase Admin credentials:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

The PWA manifest gate is local and green; guarded launch should still fail closed until the operator supplies a real service-account file outside the repository and reruns strict preflight.
