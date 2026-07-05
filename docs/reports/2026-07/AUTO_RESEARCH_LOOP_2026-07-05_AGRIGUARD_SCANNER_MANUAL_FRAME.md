# AutoResearch Loop: AgriGuard Scanner Manual Frame

Date: 2026-07-05
Scope: AgriGuard scanner mobile manual fallback
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-readiness polish on the QR scanner path. On a 390px mobile viewport, the manual fallback input was visible but the `Verify code` button sat below the first viewport, forcing no-camera users to scroll before submitting a code.

## Source-Backed Pattern

The loop follows the local AutoResearch/Karpathy workflow and the refreshed upstream source reference:

- `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Verified `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Applied pattern: measure the real scanner page, make a reversible mobile-only layout variant, adopt only after the manual fallback button becomes visible and browser/smoke guardrails stay green.

## Baseline

Artifacts:

- Metrics: `var/agriguard-scanner-mobile-manual-baseline.json`
- Screenshot: `var/agriguard-scanner-mobile-manual-baseline/scanner-manual-baseline.png`
- Original smoke screenshot: `var/agriguard-browser-smoke-suite-consumer-verify-heading-compact/qr-path-screens/scan.png`

Baseline measurement on `/scan` at `390x844`:

- Document scroll width: `390`
- Document scroll height: `1047`
- Scanner frame: `308px x 308px`
- Manual input bottom: `798px`
- Verify button top: `857px`
- Verify button bottom: `893px`
- Verify button fully visible: `false`

User impact: camera-unavailable users could see the manual input, but not the complete submit button in the first viewport.

## A/B Decision

Chosen variant: compact only the mobile scan frame while preserving the full frame from `sm` upward.

- Scanner frame: `max-w-[248px] sm:max-w-none`
- Frame stays square via `aspect-square`
- Frame remains centered with `mx-auto`

Rejected alternative: reducing all scanner card padding. That would enlarge the scan frame on mobile and not reliably expose the button. The defect was vertical space consumed by the square frame.

## Implementation

Files changed:

- `apps/AgriGuard/frontend/src/components/QRReader.jsx`
- `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`

Behavioral contract added:

- `scanner-frame` asserts `max-w-[248px]` and `sm:max-w-none`.

## Variant Evidence

Artifacts:

- Metrics: `var/agriguard-scanner-mobile-manual-compact-frame.json`
- Screenshot: `var/agriguard-scanner-mobile-manual-compact-frame/scanner-manual-compact-frame.png`
- Browser suite: `var/agriguard-browser-smoke-suite-scanner-manual-compact-frame.json`
- Browser screenshots: `var/agriguard-browser-smoke-suite-scanner-manual-compact-frame/`
- AgriGuard smoke: `var/workspace-smoke-agriguard-scanner-manual-compact-frame.json`
- Workspace smoke: `var/workspace-smoke-scanner-manual-compact-frame.json`

Post-change measurement on `/scan` at `390x844`:

- Document scroll width: `390`
- Document scroll height: `987`
- Scanner frame: `248px x 248px`
- Manual input bottom: `738px`
- Verify button top: `797px`
- Verify button bottom: `833px`
- Verify button fully visible: `true`

The scan target remains visually prominent, and the complete manual verification submit button is visible in the first mobile viewport.

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- QRReader
```

Result: `1` test file passed, `13` tests passed.

Mobile browser smoke:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-scanner-manual-compact-frame.json --output-dir var\agriguard-browser-smoke-suite-scanner-manual-compact-frame --timeout-ms 30000
```

Result: `6/6` steps, `135/135` checks, `18/18` screenshot artifacts.

AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-scanner-manual-compact-frame.json
```

Result: `5/5` checks.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-scanner-manual-compact-frame.json
```

Result: `9/9` checks.

## Remaining Blocker

Local product hardening remains green. Production launch readiness is still externally blocked on operator-provided Firebase Admin/service-account configuration for protected admin paths.
