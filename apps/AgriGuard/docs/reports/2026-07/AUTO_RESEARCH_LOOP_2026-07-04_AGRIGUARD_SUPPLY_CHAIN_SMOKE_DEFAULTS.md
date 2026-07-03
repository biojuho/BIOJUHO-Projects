# AutoResearch Loop - AgriGuard Supply-Chain Smoke Defaults

Date: 2026-07-04
App: AgriGuard
Cycle: Operator browser-smoke reliability

## Baseline

The README supply-chain browser smoke command can be run without an explicit `--operator-token`. In the local dev-fallback launch setup, that made the browser open `/supply-chain` without a stored operator token, so protected product paging returned 401.

Baseline command:

`python scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --mobile --json-out ..\var\agriguard-supply-defaults-baseline.json --screenshot ..\var\agriguard-supply-defaults-baseline.png --timeout-ms 30000`

Result: `8/14 PASS`.

Failed checks included:

- `initial_page_starts_at_first_product`: saw `Showing 0-0 of 0 products`
- `initial_renders_at_most_twenty_product_cards`: saw `0 product links`
- `products_page_endpoint_used`: saw `0 successful page / 0 fallback`
- `no_console_warnings_or_errors`: one 401 console error

## Variant

Aligned `supply_chain_browser_smoke.py` with the other authenticated local browser smokes:

- Default `--operator-token` now resolves to `AGRIGUARD_BROWSER_OPERATOR_TOKEN` or `browser-smoke-token`.
- The token remains non-secret; it is useful only when the backend is explicitly running with dev/test auth fallback.
- Explicit `--operator-token` still overrides the default for real authenticated environments.

## Evidence

- `python -m py_compile scripts/supply_chain_browser_smoke.py backend/tests/test_smoke.py`
  - Status: pass
- `python -m pytest backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-supply-defaults"`
  - Result: `15 passed`
- Mobile supply-chain smoke with no explicit token flag:
  - Command: `python scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain --mobile --json-out ..\var\agriguard-supply-defaults-fixed.json --screenshot ..\var\agriguard-supply-defaults-fixed.png --timeout-ms 30000`
  - Result: `21/21 PASS`
- Full AgriGuard smoke:
  - Command: `python ..\ops\scripts\run_workspace_smoke.py --scope agriguard --json-out ..\var\workspace-smoke-agriguard-supply-defaults.json`
  - Result: `passed=5, failed=0, total=5`

## Decision

Adopt the supply-chain browser-smoke default hardening. A no-flag local smoke now exercises the intended authenticated operator paging/search path instead of producing an empty unauthenticated product list.
