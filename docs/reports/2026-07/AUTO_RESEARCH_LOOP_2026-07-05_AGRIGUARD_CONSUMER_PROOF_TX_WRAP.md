# AutoResearch Loop - AgriGuard Consumer Proof TX Wrap

Date: 2026-07-05

## Objective

Continue launch-readiness hardening for the public `/verify/:qrToken` page by preventing late scanner errors from leaking into the consumer page and making blockchain proof transaction rows mobile-safe.

## Source Pattern

- External reference checked this loop: `Veritas-7/autoresearch-skill-system`
- Refreshed upstream commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local skill used: `D:\AI project\.agents\skills\auto-research-karpathy\SKILL.md`

## Baseline

After the initial toast-clear fix, a QR path rerun showed the underlying race could still happen: the scanner could emit a late camera error after manual recovery had already started. The consumer verification page also rendered proof transaction rows without an explicit wrapping contract.

This was a launch-readiness issue because the consumer proof page must remain stable after scan/manual recovery and must not clip blockchain evidence on mobile.

## A/B Decision

- Variant A: clear stale toasts only after entering the consumer route and keep proof TX rows without a wrapping assertion.
- Variant B: ignore late scanner errors once scan/manual recovery has claimed the session, clear stale toasts before success navigation, and wrap proof TX rows.

Adopted Variant B.

Implementation details:

- `apps/AgriGuard/frontend/src/components/QRReader.jsx`
  - Destructures `hideToast` from the toast context.
  - Clears stale toasts before success navigation.
  - Ignores scanner `onError` callbacks after `scanHandledRef.current` is set or scanning is no longer active.
- `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`
  - Adds a regression test that manually verifies a token, then fires a late scanner error and asserts no camera error is shown.
- `apps/AgriGuard/frontend/src/components/ConsumerVerify.jsx`
  - Adds `break-all` to blockchain proof transaction rows.
- `apps/AgriGuard/frontend/src/components/ConsumerVerify.test.jsx`
  - Uses a full-length proof transaction hash and asserts the proof TX row has `break-all`.

## Adopted Variant Evidence

Targeted QR path proof:

- JSON: `var\agriguard-consumer-proof-tx-wrap-qr-path.json`
- DOM metrics: `var\agriguard-consumer-proof-tx-wrap.json`
- Screenshot: `var\agriguard-consumer-proof-tx-wrap\blockchain-proof-tx-row-visible.png`

Observed metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- `bodyContainsCameraError`: `false`
- `txClass`: `mt-1 break-all font-mono text-xs text-slate-600`
- `txWhiteSpace`: `normal`
- `txOverflow`: `visible`
- `txTextOverflow`: `clip`

## Verification

Focused frontend tests:

```powershell
npm.cmd run test -- QRReader ConsumerVerify
```

Result:

- `2 passed`
- `15 passed`

QR path browser smoke:

```powershell
python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-consumer-proof-tx-wrap-qr-path.json --screenshot-dir var\agriguard-consumer-proof-tx-wrap-qr-path --timeout-ms 30000
```

Result:

- `22/22` checks passed

Mobile browser suite:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-consumer-proof-tx-wrap.json --output-dir var\agriguard-browser-smoke-suite-consumer-proof-tx-wrap --timeout-ms 30000
```

Result:

- `6/6` flows passed
- `135/135` checks passed
- `18/18` screenshot artifacts passed

Canonical AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-consumer-proof-tx-wrap.json
```

Result:

- `5/5` checks passed
- elapsed `6m9s`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-consumer-proof-tx-wrap.json
```

Result:

- `9/9` checks passed
- elapsed `2m56s`

## Remaining External Blocker

Local product hardening and verification are green for this loop. Full launch readiness still remains externally blocked on the Firebase Admin service account / operator token environment needed for production-grade protected admin paths.
