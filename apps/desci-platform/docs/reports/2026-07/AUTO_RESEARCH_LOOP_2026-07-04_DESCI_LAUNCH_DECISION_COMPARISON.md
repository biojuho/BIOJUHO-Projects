# AutoResearch Loop - DeSci Launch Decision Comparison

Date: 2026-07-04

## Goal

Prevent the product launch gate from passing when the live `/launch` API and
the browser dashboard launch-control evidence disagree on the operator-facing
launch decision.

## A/B Decision

- Baseline: release gate compared live and browser launch action IDs/env keys,
  but did not compare release decision, operator phase, readiness status,
  blocker/action counts, readiness summary, or score.
- Variant: add `launch_decision_comparison` to the parent release-gate JSON and
  a dedicated `--runtime-smoke-strict-launch-decision` fail-closed mode.
- Decision: keep the variant. It catches cases where action coverage still
  matches but the dashboard tells the operator a different go/no-go story than
  the live API.

## Changes

- `scripts/release_gate.py`
  - Adds `launch_decision_comparison(...)`.
  - Compares live vs browser release decision, operator phase, readiness status,
    launch blocker count, next-action count, readiness summary, and score.
  - Adds `strict_launch_decision_consistency_result(...)`.
  - Adds `--runtime-smoke-strict-launch-decision`.
  - Documents the new parent JSON object in `json_report_schema()`.
- `backend/tests/test_release_gate.py`
  - Adds comparison drift tests.
  - Adds strict-result pass/fail tests.
  - Adds CLI strict launch-decision regression.
  - Extends parent report and schema assertions.

## Verification

- `python -m py_compile scripts\release_gate.py`
  - Pass.
- `python -m pytest backend\tests\test_release_gate.py -q`
  - `115 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-screenshot-dir var\release-gate-launch-decision-comparison-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-launch-decision-comparison-2026-07-04.json`
  - Release gate OK.
  - `launch_action_coverage_comparison.status=match`.
  - `launch_decision_comparison.status=match`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-smoke-strict-action-coverage --runtime-smoke-strict-launch-decision --runtime-browser-screenshot-dir var\release-gate-launch-decision-strict-screenshots-2026-07-04 --runtime-evidence-dir var --json-out var\release-gate-launch-decision-strict-2026-07-04.json`
  - Release gate OK.
  - Parent summary: `passed=2`, `failed=0`.
  - Decision match flags all true: release decision, operator phase,
    readiness status, launch blocker count, next-action count, readiness
    summary, and score.

## Artifacts

- `var\release-gate-launch-decision-comparison-2026-07-04.json`
- `var\release-gate-launch-decision-comparison-screenshots-2026-07-04\dashboard-readiness-refresh.png`
- `var\release-gate-launch-decision-strict-2026-07-04.json`
- `var\release-gate-launch-decision-strict-screenshots-2026-07-04\dashboard-readiness-refresh.png`
