# AutoResearch Loop: DeSci Release Gate Env Handoff Summary

Date: 2026-07-04

## Objective

Close the next DeSci launch-evidence gap after adding product-smoke
`launch_env_handoff`. Operators should not need to open child smoke artifacts
to find the secure placeholder-only launch env checklist.

## A/B Contract

- Baseline: `product_smoke.py` emits `launch_env_handoff`, but the release-gate
  parent JSON only promotes `launch_handoff_summary`, `ready_web3_summary`, and
  `ready_launch_action_coverage_summary`.
- Variant: validate `launch_env_handoff` when present and promote a top-level
  `launch_env_handoff_summary` into release-gate parent JSON.
- Primary KPI: release-gate parent JSON exposes required env keys, optional env
  keys, action IDs, placeholder-only copy lines, and `secret_policy` directly.
- Guardrails: malformed env handoff artifacts must fail validation; copy lines
  must not contain raw URLs, addresses, or secret-shaped values; DeSci workspace
  and browser launch-click smoke must remain green.

## Implementation

- Added release-gate validation for product-smoke `launch_env_handoff` shape.
- Added artifact extraction and parent summary promotion for
  `launch_env_handoff_summary`.
- Added report-schema coverage for the new parent summary.
- Added regression coverage for malformed status/copy-line handoff payloads.

The new validation is backward-compatible for older product-smoke artifacts:
the field is validated when present and promoted only when the artifact itself
passes validation.

## Verification

- `python -m pytest backend/tests/test_release_gate.py -q`
  - Result: `102 passed in 1.64s`
- `python -m pytest backend/tests/test_product_smoke_launch_env_handoff.py -q`
  - Result: `2 passed in 0.30s`
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --strict-ready --json-out var/product-smoke-launch-env-release-gate-summary-2026-07-04.json`
  - Expected fail-closed result: `ready` blocked and `launch` no-go on
    `auth`, `stripe`, `cors`.
  - Child handoff remained placeholder-only:
    `status=blocked`, `operator_copy_lines=17`, `bad_copy_lines=[]`.
- `python scripts/release_gate.py --runtime-smoke --runtime-smoke-step product --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --json-out var/release-gate-launch-env-handoff-summary-2026-07-04.json`
  - Result: release gate product step passed.
  - Parent summary:
    `status=blocked`, `secret_policy=placeholder_only_no_secret_values`,
    required env keys matched `auth`, `stripe`, and `cors`, optional env keys
    matched `rabbitmq`, `ipfs`, and `grobid`, and `bad_copy_lines=[]`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var/browser-smoke-launch-env-release-gate-summary-2026-07-04.json --trace-on-failure-dir var/browser-smoke-launch-env-release-gate-summary-2026-07-04-traces`
  - Result: `9/9` launch click checks OK.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-launch-env-release-gate-summary-2026-07-04.json`
  - Result: `8/8 passed`.
- `git diff --check -- scripts/release_gate.py backend/tests/test_release_gate.py`
  - Result: passed.

Secret scan note: high-risk pattern scan matched only the scanner regex itself
and intentional negative test fixtures in `backend/tests/test_release_gate.py`.

## Decision

Adopted. Release-gate parent evidence now carries the same copy-ready,
placeholder-only env handoff as product smoke. Production release remains
blocked by real external configuration for auth, Stripe, and CORS, which is the
intended fail-closed state until operator-owned values are installed.
