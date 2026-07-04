# AutoResearch Loop: DeSci Release-Gate Browser Env Handoff

Date: 2026-07-04

## Objective

Connect the browser-clicked dashboard env handoff evidence to release-gate
summaries so it is not isolated inside a browser-smoke JSON artifact.

## A/B Contract

- Baseline: product-smoke top-level `launch_env_handoff` was summarized by
  release-gate, while browser-smoke nested
  `launch_control.launch_env_handoff` was only preserved in its own artifact.
- Variant: align the browser-smoke nested handoff schema with product-smoke
  action-id fields and let release-gate validate and summarize the nested
  browser evidence.
- Primary KPI: a valid browser-smoke artifact can produce
  `launch_env_handoff_summary` with browser-click evidence source and
  placeholder-only copy lines.
- Guardrails: product-smoke top-level handoff validation remains unchanged, and
  malformed browser nested handoffs fail closed through the browser-smoke schema
  validator.

## Implementation

- Added `required_action_ids` and `optional_action_ids` to browser-smoke nested
  launch env handoff evidence.
- Refactored release-gate launch env handoff validation into a shared helper.
- Validated `launch_control.launch_env_handoff` in browser-smoke artifacts.
- Taught release-gate artifact extraction and summary generation to read either
  top-level product-smoke handoff evidence or nested browser-smoke evidence.

## Verification

- `python -m py_compile scripts/browser_smoke.py scripts/release_gate.py`
  - Result: passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_release_gate.py -q`
  - Result: `146 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --json-out var/browser-smoke-dashboard-env-handoff-release-gate-2026-07-04.json --trace-on-failure-dir var/browser-smoke-dashboard-env-handoff-release-gate-2026-07-04-traces`
  - Result: OK.
  - Nested evidence source: `dashboard-readiness-refresh-browser-click`.
  - Required action IDs: `auth`, `stripe`, `cors`.
  - Optional action IDs: `rabbitmq`, `ipfs`, `grobid`.
  - `bad_copy_lines=[]`.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5173 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-evidence-dir var --json-out var/release-gate-browser-env-handoff-summary-2026-07-04.json`
  - Result: OK, one `browser-smoke` step passed.
  - Parent summary source: `dashboard-readiness-refresh-browser-click`.
  - Parent summary status: `blocked`.
  - Parent summary line count: `19`.

## Decision

Adopted. The browser-clicked dashboard handoff now feeds the same release-gate
summary path as product-smoke handoff evidence, while preserving source
attribution for later audits.
