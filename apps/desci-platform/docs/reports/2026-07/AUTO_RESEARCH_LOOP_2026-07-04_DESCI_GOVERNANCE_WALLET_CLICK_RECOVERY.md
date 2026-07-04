# AutoResearch Loop: Governance Wallet Click Recovery

Date: 2026-07-04

## Objective

Recover the DeSci launch-click suite after current app-click evidence showed the
Governance no-wallet path failing on wallet-required guidance detection.

## Scope

Owned path changed in this cycle:

- `scripts/browser_smoke.py`

The Governance UI already rendered `data-testid="governance-wallet-required"`
with the required guidance. The fix keeps the app behavior unchanged and makes
the browser smoke wait for that canonical status region before running the
legacy broad text probe.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern is bounded A/B improvement: current app-click evidence
found a launch-risk regression; the variant was adopted only after the same
click path and canonical smoke checks passed.

## A/B Decision

Baseline:

- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\browser-smoke-launch-click-current-2026-07-04-next.json --screenshot-dir var\browser-smoke-launch-click-current-2026-07-04-next-screens --trace-on-failure-dir var\browser-smoke-launch-click-current-2026-07-04-next-traces`
  - Expected failure before the fix.
  - Result: `43 passed`, `1 failed`.
  - Failure: `governance-wallet-required: missing wallet-required governance guidance`.
  - Trace: `var\browser-smoke-launch-click-current-2026-07-04-next-traces\governance-wallet-required.trace.zip`.

Variant:

- Wait for `governance-wallet-required` to be visible and read its text before
  the broad `_any_text_visible` check.
- Preserve the existing explicit status-region text assertions.

Decision rule:

- Adopt if the focused Governance click check passes, the full launch-click
  suite returns to 44/44, and the DeSci smoke scope remains green.

Result: adopted.

## Verification

- `python -m py_compile scripts\browser_smoke.py`
  - Exit code `0`.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check governance-wallet-required --json-out var\browser-smoke-governance-wallet-required-fix-2026-07-04.json --screenshot-dir var\browser-smoke-governance-wallet-required-fix-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-governance-wallet-required-fix-2026-07-04-traces`
  - Exit code `0`.
  - `governance-wallet-required OK`.
- `python -m pytest backend\tests\test_browser_smoke.py -q`
  - `50 passed`.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\browser-smoke-launch-click-governance-wallet-fix-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-governance-wallet-fix-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-governance-wallet-fix-2026-07-04-traces`
  - Exit code `0`.
  - `44 passed`, `0 failed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-governance-wallet-click-fix-2026-07-04.json`
  - `8 passed`, `0 failed`.

## Current Boundary

The user-facing launch-click suite is green again. Public launch remains blocked
by external provider authentication and real deployment secrets, not by this
Governance wallet-required click path.

## Next Cycle

Continue app-click exploration and look for current-state launch gaps outside
the already-recovered Governance wallet path.
