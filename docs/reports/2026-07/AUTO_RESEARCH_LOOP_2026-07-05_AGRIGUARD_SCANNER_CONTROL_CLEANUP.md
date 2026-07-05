# AutoResearch Loop - AgriGuard Scanner Control Cleanup

Date: 2026-07-05

## Objective

Continue launch-readiness hardening on the public AgriGuard QR scan path by removing confusing mobile scanner chrome while preserving scan, retry, manual-entry, and analytics behavior.

## Source Pattern

- External reference checked this loop: `Veritas-7/autoresearch-skill-system`
- Refreshed upstream commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local skill used: `D:\AI project\.agents\skills\auto-research-karpathy\SKILL.md`
- Local primary API reference used: `apps\AgriGuard\frontend\node_modules\@yudiel\react-qr-scanner\README.md`
  - The installed scanner package documents `components.onOff` as the built-in camera on/off button.

## Baseline

The mobile scanner route was functionally passing, but the scan frame exposed the scanner library's built-in camera toggle as an unstyled button inside the capture area.

Baseline evidence:

- Screenshot: `var\agriguard-browser-smoke-suite-coldchain-stat-wrap\nav-screens\scanner.png`
- DOM inspection: `var\agriguard-scanner-dom-inspection.json`
- Visible control: `button[aria-label="Turn camera on"]`
- Control position: `left=303`, `top=530`, `right=339`, `bottom=566`

This was a launch-readiness issue because the public QR scan flow already has app-owned recovery UI (`Retry scan`) and manual verification fallback. The extra library chrome looked detached from the AgriGuard interface and could be mistaken for a capture target or broken overlay.

## A/B Decision

- Variant A: keep the library's built-in camera on/off control inside the scan frame.
- Variant B: disable only `components.onOff` and keep the app-owned retry/manual recovery controls.

Adopted Variant B.

Implementation details:

- `apps/AgriGuard/frontend/src/components/QRReader.jsx`
  - Changed scanner config from `onOff: true` to `onOff: false`.
  - Kept `audio: false`, `torch: true`, `zoom: true`, and `finder: true`.
- `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`
  - Captures the scanner config in the test mock.
  - Adds a regression assertion that `onOff` remains disabled while the other scanner affordances stay configured.

## Adopted Variant Evidence

Live mobile DOM proof:

- Metrics JSON: `var\agriguard-scanner-control-cleanup.json`
- Active fake-camera metrics JSON: `var\agriguard-scanner-active-control-cleanup.json`
- Error/retry screenshot: `var\agriguard-scanner-control-cleanup\scan-mobile-no-camera-toggle.png`
- Active scan screenshot: `var\agriguard-scanner-control-cleanup\scan-mobile-active-no-camera-toggle.png`

Observed active-scan metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- `hasVideo`: `true`
- `hasCameraToggle`: `false`
- `visibleScannerButtons`: `[]`

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- QRReader
```

Result:

- `1 passed`
- `12 passed`

Mobile browser suite:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-scanner-control-cleanup.json --output-dir var\agriguard-browser-smoke-suite-scanner-control-cleanup --timeout-ms 30000
```

Result:

- `6/6` flows passed
- `135/135` checks passed
- `18/18` screenshot artifacts passed

Canonical AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-scanner-control-cleanup.json
```

Result:

- `5/5` checks passed
- elapsed `5m45s`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-scanner-control-cleanup.json
```

Result:

- `9/9` checks passed
- elapsed `2m51s`

## Remaining External Blocker

Local product hardening and verification are green for this loop. Full launch readiness still remains externally blocked on the Firebase Admin service account / operator token environment needed for production-grade protected admin paths.
