# AutoResearch Loop: Launch Click Complete Action Surface

Date: 2026-07-04

## Objective

Promote the remaining authenticated browser action checks into the DeSci
launch-click preset so the preset covers every current direct-click action
surface instead of a curated subset.

## Scope and Owned Paths

- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

## A/B Hypothesis

- Baseline: the launch-click preset covered 36 app-click paths after the wallet
  and governance expansion, but 8 existing action checks still required manual
  selection.
- Variant: promote investor filtering/fallback, pricing/public layout,
  dashboard clipboard/source-link fallback, and wallet provider failure/switch
  checks into `--launch-click-suite`.
- Decision rule: adopt only if the candidate checks pass, the preset executes
  every action check in deterministic runner order, full launch-click evidence
  passes, and canonical DeSci smoke remains green.

## Candidate Paths

- `investors-filter-directory`
- `investors-seed-directory-fallback`
- `pricing-layout-inset`
- `public-touch-targets`
- `dashboard-readiness-copy-failure`
- `dashboard-recommendation-source-link-fallback`
- `wallet-extension-missing`
- `wallet-provider-amoy`

## Result

Adopted.

The canonical launch-click preset now executes 44 checks, matching the complete
authenticated action-check surface available in `browser_smoke.py`.

During the first expanded run, `pricing-layout-inset` exposed a fixture
isolation gap: `/pricing` could emit an unmocked `/subscription/tier` network
error while the layout assertion was running. The layout and public touch-target
checks now stub `/subscription/tier` with the same free-tier fixture pattern used
by checkout checks.

## Verification

- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --timeout 45 --only-check investors-filter-directory --only-check investors-seed-directory-fallback --only-check pricing-layout-inset --only-check public-touch-targets --only-check dashboard-readiness-copy-failure --only-check dashboard-recommendation-source-link-fallback --only-check wallet-extension-missing --only-check wallet-provider-amoy --json-out var\browser-smoke-launch-remaining-candidates-2026-07-04.json --screenshot-dir var\browser-smoke-launch-remaining-candidates-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-remaining-candidates-2026-07-04-traces` -> candidate 8/8 passed.
- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q` -> 50 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --timeout 45 --only-check pricing-layout-inset --only-check public-touch-targets --json-out var\browser-smoke-pricing-public-layout-candidates-2026-07-04.json --screenshot-dir var\browser-smoke-pricing-public-layout-candidates-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-pricing-public-layout-candidates-2026-07-04-traces` -> targeted layout rerun 2/2 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var\browser-smoke-launch-click-complete-action-surface-2026-07-04-rerun.json --screenshot-dir var\browser-smoke-launch-click-complete-action-surface-2026-07-04-rerun-screens --trace-on-failure-dir var\browser-smoke-launch-click-complete-action-surface-2026-07-04-rerun-traces` -> expanded 44/44 passed; 44 screenshots captured.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-launch-click-complete-action-surface-2026-07-04.json` -> 8 passed, 0 failed.

## Remaining Launch Boundary

This completes the current local browser action preset, but it is still local
and fixture-backed evidence. External hosted provider authentication/config and
live deployment readiness remain separate launch blockers.

## Next Cycle

Shift from broad click coverage to the next launch-risk boundary: hosted deploy
readiness, external provider recovery, or replacing fixture-only checks with
live-environment proof where credentials are available.
