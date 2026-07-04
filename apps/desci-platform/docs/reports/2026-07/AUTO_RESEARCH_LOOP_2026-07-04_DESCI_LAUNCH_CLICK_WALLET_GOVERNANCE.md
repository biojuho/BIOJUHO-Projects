# AutoResearch Loop: Launch Click Wallet and Governance Workflows

Date: 2026-07-04

## Objective

Extend DeSci launch-click evidence into the authenticated wallet, governance,
AI Lab, peer-review, MyLab minting, VC portal, and mobile protected-layout paths
that must survive real operator clicks before launch.

## Scope and Owned Paths

- `frontend/src/components/Governance.jsx`
- `frontend/src/__tests__/components/Governance.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

## A/B Hypothesis

- Baseline: candidate app-click checks mostly passed, but
  `governance-wallet-required` failed because the no-wallet governance state was
  not exposed as a stable, automation-addressable guidance region.
- Variant: add a visible announced governance wallet-required status region,
  preserve disabled create/vote actions before wallet connection, assert the
  guidance region in browser smoke, and promote the passing wallet/governance
  candidate set into the launch-click preset.
- Decision rule: adopt only if the candidate set passes 13/13, focused frontend
  and backend tests pass, the expanded launch-click preset passes with all checks
  executed, and canonical DeSci smoke remains green.

## Result

Adopted.

The canonical launch-click preset now executes 36 checks and includes these new
paths:

- `protected-mobile-layout-inset`
- `upload-submit-wallet-receipt`
- `ai-lab-readiness`
- `ai-lab-agent-error-visible`
- `ai-lab-result-copy-failure`
- `peer-review-readiness`
- `peer-review-submit-receipt`
- `mylab-mint-wallet-required`
- `mylab-mint-success`
- `vc-portal-select`
- `governance-wallet-required`
- `governance-connected-create-vote`
- `wallet-restore-direct-governance`

## Verification

- `npm exec vitest -- run src/__tests__/components/Governance.test.jsx` -> 3 passed.
- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q` -> 49 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --timeout 45 --only-check protected-mobile-layout-inset --only-check upload-submit-wallet-receipt --only-check ai-lab-readiness --only-check ai-lab-agent-error-visible --only-check ai-lab-result-copy-failure --only-check peer-review-readiness --only-check peer-review-submit-receipt --only-check mylab-mint-wallet-required --only-check mylab-mint-success --only-check vc-portal-select --only-check governance-wallet-required --only-check governance-connected-create-vote --only-check wallet-restore-direct-governance --json-out var\browser-smoke-wallet-governance-launch-candidates-2026-07-04-rerun.json --screenshot-dir var\browser-smoke-wallet-governance-launch-candidates-2026-07-04-rerun-screens --trace-on-failure-dir var\browser-smoke-wallet-governance-launch-candidates-2026-07-04-rerun-traces` -> candidate 13/13 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var\browser-smoke-launch-click-wallet-governance-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-wallet-governance-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-wallet-governance-2026-07-04-traces` -> expanded 36/36 passed; 36 screenshots captured.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-launch-click-wallet-governance-2026-07-04.json` -> 8 passed, 0 failed.

## Remaining Launch Boundary

This cycle improves local app-click and repository-owned evidence. It does not
remove the external launch blockers around hosted provider auth/config and live
deployment readiness.

## Next Cycle

Continue the AutoResearch loop against the next launch-risk surface: direct
checkout/subscription persistence, hosted provider readiness, or any remaining
route with mocked-only browser evidence.
