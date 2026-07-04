# AutoResearch Loop: Launch Click Research Workflow

Date: 2026-07-04

## Objective

Extend DeSci launch-click evidence from pricing/upload readiness into the
research conversion paths that users reach after finding notices, preparing RFPs,
and generating BioLinker proposals.

## Scope and Owned Paths

- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

## A/B Hypothesis

- Baseline: the launch-click preset covered pricing resilience and upload/asset
  paths, but it did not include authenticated BioLinker proposal or notices
  discovery workflows.
- Variant: include BioLinker RFP readiness, paper context handoff, proposal copy
  failure handling, proposal export popup-block handling, empty-match next
  actions, notices discovery readiness, notices-to-BioLinker handoff, notices
  source-link fallback, and notices bridge navigation.
- Decision rule: adopt only if all candidate checks pass individually, the
  expanded launch-click preset passes with all checks executed, focused tests
  pass, and canonical DeSci smoke remains green.

## Result

Adopted.

The canonical launch-click preset now executes 23 checks and includes these
research conversion paths:

- `biolinker-rfp-readiness`
- `biolinker-paper-context-handoff`
- `biolinker-proposal-clipboard-failure`
- `biolinker-proposal-export-popup-blocked`
- `biolinker-empty-match-next-actions`
- `notices-discovery-readiness`
- `notices-discovery-biolinker-handoff`
- `notices-source-link-fallback`
- `notices-biolinker-bridge`

## Verification

- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --timeout 45 --only-check biolinker-rfp-readiness --only-check biolinker-paper-context-handoff --only-check biolinker-proposal-clipboard-failure --only-check biolinker-proposal-export-popup-blocked --only-check biolinker-empty-match-next-actions --only-check notices-discovery-readiness --only-check notices-discovery-biolinker-handoff --only-check notices-source-link-fallback --only-check notices-biolinker-bridge --json-out var\browser-smoke-research-workflow-launch-candidates-2026-07-04.json --screenshot-dir var\browser-smoke-research-workflow-launch-candidates-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-research-workflow-launch-candidates-2026-07-04-traces` -> candidate 9/9 passed.
- `python -m py_compile scripts\browser_smoke.py`
- `python -m pytest backend\tests\test_browser_smoke.py -q` -> 48 passed.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var\browser-smoke-launch-click-research-workflow-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-research-workflow-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-research-workflow-2026-07-04-traces` -> expanded 23/23 passed; 23 screenshots captured.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-launch-click-research-workflow-2026-07-04-rerun.json` -> 8 passed, 0 failed.

## Next Cycle

Continue expanding direct app-click coverage into wallet/governance, peer
review, MyLab minting, VC portal, and AI Lab workflows. Those paths are already
available as authenticated action checks and should be promoted into the launch
preset only after same-sample candidate evidence passes.
