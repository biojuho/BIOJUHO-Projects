# AutoResearch Loop - DeSci Dashboard Copy-All Evidence

Date: 2026-07-04

## Goal

Make the dashboard launch-control browser evidence prove the bulk "Copy all"
operator handoff works, not only the individual launch-action copy buttons.

## A/B Decision

- Baseline: `dashboard-readiness-refresh` clicked the copy-all button and failed
  on bad payload/feedback, but the release artifact only summarized individual
  launch-action copy coverage.
- Variant: emit `launch_control.launch_action_copy_all`, require it in
  `release_gate.py`, flatten it into artifact reports, and expose it under
  `browser_launch_control_summary.launch_action_copy_all`.
- Decision: keep the variant. It makes the operator bulk-copy path auditable at
  release-gate level and fails closed if feedback is not verified, a secret-like
  value is detected, or any expected launch action is absent from the copied
  packet.

## Changes

- `scripts/browser_smoke.py`
  - Records `launch_action_copy_all` with `ok`, `source`, `secret_policy`,
    `feedback_verified`, `secret_leak_detected`, expected/validated/missing
    action IDs, and count fields.
  - Verifies the copy-all fragment map matches the individual launch-action ID
    list so future action additions cannot be silently skipped.
- `scripts/release_gate.py`
  - Requires `launch_control.launch_action_copy_all` for
    `dashboard-readiness-refresh` artifacts.
  - Validates action IDs/counts, feedback, secret policy, and no missing IDs.
  - Adds artifact report fields and JSON schema coverage for the parent summary.
- Tests
  - Producer-side browser-smoke JSON contract coverage.
  - Release-gate missing-copy-all regression.
  - Parent release-gate summary/schema assertions.

## Verification

- `python -m py_compile scripts\browser_smoke.py scripts\release_gate.py`
  - Pass.
- `python -m pytest backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py -q`
  - `157 passed`.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --screenshot-dir var\browser-smoke-dashboard-copy-all-evidence-2026-07-04 --json-out var\browser-smoke-dashboard-copy-all-evidence-2026-07-04.json --trace-on-failure-dir var\browser-smoke-dashboard-copy-all-evidence-2026-07-04-traces`
  - `dashboard-readiness-refresh OK`.
  - `launch_action_copy_all.ok=true`.
  - `validated_action_ids=["auth","stripe","cors","rabbitmq","ipfs","grobid"]`.
  - `missing_action_ids=[]`.
  - `feedback_verified=true`.
  - `secret_leak_detected=false`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-dashboard-copy-all-evidence-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-dashboard-copy-all-evidence-2026-07-04.json`
  - Release gate OK.
  - Parent `browser_launch_control_summary.launch_action_copy_all` records all
    six validated IDs, no missing IDs, verified feedback, and no secret leak.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-dashboard-copy-all-evidence-2026-07-04.json`
  - `passed=8, failed=0, total=8`.

## Artifacts

- `var\browser-smoke-dashboard-copy-all-evidence-2026-07-04.json`
- `var\browser-smoke-dashboard-copy-all-evidence-2026-07-04\dashboard-readiness-refresh.png`
- `var\release-gate-dashboard-copy-all-evidence-2026-07-04.json`
- `var\release-gate-dashboard-copy-all-evidence-screenshots-2026-07-04\dashboard-readiness-refresh.png`
- `var\workspace-smoke-desci-dashboard-copy-all-evidence-2026-07-04.json`
