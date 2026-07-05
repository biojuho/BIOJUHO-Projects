# AutoResearch Loop: AgriGuard Consumer Verify Heading Compact

Date: 2026-07-05
Scope: AgriGuard consumer QR verification mobile trust surface
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-readiness polish on the public QR verification path. The consumer trust headline `Needs more evidence` wrapped to two lines on a 390px mobile viewport, pushing the trust reason and evidence cards lower in the first viewport.

## Source-Backed Pattern

The loop follows the local AutoResearch/Karpathy workflow and the refreshed upstream source reference:

- `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Verified `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Applied pattern: use browser evidence from the real QR verification path, apply a minimal mobile-only type-scale variant, and adopt it only after focused and canonical smoke checks pass.

## Baseline

Artifacts:

- Metrics: `var/agriguard-consumer-verify-mobile-heading-baseline.json`
- Screenshot: `var/agriguard-consumer-verify-mobile-heading-baseline/consumer-verify-heading-baseline.png`
- Original smoke screenshot: `var/agriguard-browser-smoke-suite-admin-heading-compact/qr-path-screens/manual-verify.png`

Baseline measurement on the seeded public verification route at `390x844`:

- Document scroll width: `390`
- Trust headline text: `Needs more evidence`
- Trust headline class: `mt-3 text-2xl font-bold leading-tight`
- Trust headline width: `252px`
- Trust headline height: `60px`
- Trust headline font size: `24px`
- Trust headline line height: `30px`

User impact: the status headline wrapped in the public trust card, reducing first-viewport density before origin, batch, temperature, and last-verified evidence.

## A/B Decision

Chosen variant: mobile-first compact trust headline.

- Mobile H1: `text-xl leading-tight`
- Small breakpoint and above: `sm:text-2xl`
- Add `consumer-trust-heading` test ID for focused coverage.

Rejected alternative: changing the trust label copy. The phrase is clear and safety-oriented; the issue was mobile type scale.

## Implementation

Files changed:

- `apps/AgriGuard/frontend/src/components/ConsumerVerify.jsx`
- `apps/AgriGuard/frontend/src/components/ConsumerVerify.test.jsx`

Behavioral contract added:

- `consumer-trust-heading` asserts `text-xl` and `sm:text-2xl`.

## Variant Evidence

Artifacts:

- Metrics: `var/agriguard-consumer-verify-mobile-heading-compact.json`
- Screenshot: `var/agriguard-consumer-verify-mobile-heading-compact/consumer-verify-heading-compact.png`
- Browser suite: `var/agriguard-browser-smoke-suite-consumer-verify-heading-compact.json`
- Browser screenshots: `var/agriguard-browser-smoke-suite-consumer-verify-heading-compact/`
- AgriGuard smoke: `var/workspace-smoke-agriguard-consumer-verify-heading-compact.json`
- Workspace smoke: `var/workspace-smoke-consumer-verify-heading-compact.json`

Post-change measurement on the same route at `390x844`:

- Document scroll width: `390`
- Trust headline class: `mt-3 text-xl font-bold leading-tight sm:text-2xl`
- Trust headline width: `252px`
- Trust headline height: `25px`
- Trust headline font size: `20px`
- Trust headline line height: `25px`

The public verify card now keeps the warning headline on one line and leaves more room for the trust reason and evidence cards.

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- ConsumerVerify
```

Result: `1` test file passed, `2` tests passed.

Mobile browser smoke:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-consumer-verify-heading-compact.json --output-dir var\agriguard-browser-smoke-suite-consumer-verify-heading-compact --timeout-ms 30000
```

Result: `6/6` steps, `135/135` checks, `18/18` screenshot artifacts.

AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-consumer-verify-heading-compact.json
```

Result: `5/5` checks.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-consumer-verify-heading-compact.json
```

Result: `9/9` checks.

## Remaining Blocker

Local product hardening remains green. Production launch readiness is still externally blocked on operator-provided Firebase Admin/service-account configuration for protected admin paths.
