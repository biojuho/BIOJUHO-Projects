# AutoResearch Loop - AgriGuard Consumer Verify Unavailable Browser Smoke

Date: 2026-07-04
App: AgriGuard
Cycle: Public QR unavailable-state coverage

## Source-Backed Rationale

The refreshed GitHub comparison highlighted offline or low-connectivity consumer verification as the strongest remaining source-backed gap. AgriGuard already had a public verify unavailable state in the component, but no browser smoke proved that route when the backend verification API is down.

## Baseline

No dedicated browser check existed for `/verify/:token` with the frontend running and backend verification unavailable. A regression could blank the page, hide retry/scan recovery, or render product evidence for a failed verification request without failing the existing seeded QR happy-path smoke.

## Variant

Added `scripts/consumer_verify_unavailable_browser_smoke.py`:

- Opens `/verify/unavailable-smoke-token` on a mobile viewport.
- Runs with backend `8002` intentionally down.
- Asserts `Verification unavailable`, network recovery copy, Retry, and Scan recovery are visible.
- Asserts product evidence sections such as `Batch and origin` and `Evidence hash` are not rendered.
- Clicks Retry and confirms another verification attempt occurs while the unavailable state remains usable.
- Records expected API request failures separately from page errors.

## Evidence

- Confirmed no backend listener on `127.0.0.1:8002`.
- `python -m py_compile scripts/consumer_verify_unavailable_browser_smoke.py backend/tests/test_smoke.py`
  - Status: pass
- `python -m pytest backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-consumer-unavailable"`
  - Result: `19 passed`
- Browser smoke:
  - Command: `python scripts/consumer_verify_unavailable_browser_smoke.py --base-url http://127.0.0.1:5174 --json-out ..\var\agriguard-consumer-verify-unavailable.json --screenshot ..\var\agriguard-consumer-verify-unavailable.png --timeout-ms 30000`
  - Result: `13/13 PASS`
- Full AgriGuard smoke:
  - Command: `python ..\ops\scripts\run_workspace_smoke.py --scope agriguard --json-out ..\var\workspace-smoke-agriguard-consumer-unavailable.json`
  - Result: `passed=5, failed=0, total=5`

## Decision

Adopt the unavailable-state browser smoke. This closes the immediate low-connectivity public verification proof gap without adding cached proof semantics before privacy, freshness, and staleness rules are explicit.
