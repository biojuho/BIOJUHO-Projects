# AgriGuard QR Manual Fallback Launch Loop

Date: 2026-07-03

## Scope

Harden the mobile QR verification path where camera access is unavailable or scanner recognition fails. This loop focused on `/scan` and the public `/verify/:qrToken` consumer path.

## Source-Backed Signals

- `nimiq/qr-scanner` documents browser camera and worker constraints, reinforcing the need for a non-camera fallback: https://github.com/nimiq/qr-scanner
- `yudielcurbelo/react-qr-scanner` is the scanner library used in AgriGuard; fallback UX is still an app responsibility: https://github.com/yudielcurbelo/react-qr-scanner
- `hyperledger-foodtraze/foodtraze-network` and related food traceability implementations show QR verification as a consumer trust surface, not just an operator tool: https://github.com/hyperledger-foodtraze/foodtraze-network
- NIST SCT4AFM provides agriculture traceability reference material that supports consumer-facing verification evidence: https://github.com/usnistgov/SCT4AFM

## A/B Browser Result

Baseline evidence: `var/agriguard-qr-path-baseline.json`

- `/scan` on a 390x844 mobile viewport showed camera failure copy and `Retry scan`.
- Baseline had `scanHasManualInput: false`, leaving users blocked when the camera was unavailable.
- Invalid `/verify/not-a-real-token` correctly rendered the public unverified state.

Variant evidence: `var/agriguard-qr-path-variant.json`

- `17/17 PASS`
- Manual input visible on `/scan`.
- Verify button disabled until input.
- Manual `mock-0` entry navigated to `/verify/mock-0?...`.
- Public verification rendered trust copy, batch evidence, and no unavailable state.
- Invalid `not-a-real-token` rendered `QR not verified` / `Unverified AgriGuard QR`.
- No console warnings or errors.
- No page errors.
- No actionable request failures.
- No horizontal overflow at 390x844.

Screenshots:

- `var/agriguard-qr-path-variant-screens/scan.png`
- `var/agriguard-qr-path-variant-screens/manual-verify.png`
- `var/agriguard-qr-path-variant-screens/invalid-verify.png`

## Adopted Change

- Added a manual verification form to `QRReader`.
- Manual input accepts full verification URLs, relative `/verify/...` paths, `agri://verify/...`, and bare token values.
- Raw scanner payloads still reject non-URL text unless they parse to a supported AgriGuard route, preserving invalid-scan telemetry.
- Manual analytics is non-blocking so verification navigation is not held hostage by event logging.
- Added a durable browser smoke script: `apps/AgriGuard/scripts/qr_path_browser_smoke.py`.

## Verification

- `npm run test -- QRReader`: 8/8 tests passed.
- `python -m py_compile apps/AgriGuard/scripts/qr_path_browser_smoke.py`: passed.
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --json-out var/agriguard-qr-path-variant.json --screenshot-dir var/agriguard-qr-path-variant-screens --manual-token mock-0 --invalid-token not-a-real-token --viewport 390x844`: 17/17 passed.
- `npm run lint`: passed.
- `npm run build:lts`: passed after restoring the default frontend build.
- `npm run check:bundle`: passed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-qr-manual-fallback.json`: 5/5 passed.

## Notes

- A calibration run on preview port `5175` failed because backend CORS rejected that origin. The launch proof was rerun on the configured AgriGuard preview origin `5174`, where analytics and verification calls both passed.
- Existing unrelated staged report files were left out of this loop's commit.
