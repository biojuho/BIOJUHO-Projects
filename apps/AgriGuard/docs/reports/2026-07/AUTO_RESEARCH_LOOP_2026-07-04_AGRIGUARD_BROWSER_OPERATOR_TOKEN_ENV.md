# AutoResearch Loop - AgriGuard Browser Operator Token Env

Date: 2026-07-04
App: AgriGuard
Cycle: Browser-smoke staging-token reliability

## Baseline

After hardening the local no-flag browser smoke defaults, the authenticated browser scripts were inconsistent:

- `nav_browser_smoke.py` and `supply_chain_browser_smoke.py` honored `AGRIGUARD_BROWSER_OPERATOR_TOKEN`.
- `qr_path_browser_smoke.py`, `admin_routes_browser_smoke.py`, and `product_detail_browser_smoke.py` always defaulted to `browser-smoke-token` unless a caller passed `--operator-token`.

That is fine for local dev fallback, but weak for staging or real authenticated smoke runs where the operator token is intentionally injected through the environment.

## Variant

Aligned all authenticated browser smokes:

- `qr_path_browser_smoke.py`
- `admin_routes_browser_smoke.py`
- `product_detail_browser_smoke.py`

Each now resolves `--operator-token` from `AGRIGUARD_BROWSER_OPERATOR_TOKEN` first, then falls back to the non-secret local `browser-smoke-token`.

## Evidence

- `python -m py_compile scripts/admin_routes_browser_smoke.py scripts/product_detail_browser_smoke.py scripts/qr_path_browser_smoke.py backend/tests/test_smoke.py`
  - Status: pass
- `python -m pytest backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-operator-token-env"`
  - Result: `18 passed`
- Full AgriGuard smoke:
  - Command: `python ..\ops\scripts\run_workspace_smoke.py --scope agriguard --json-out ..\var\workspace-smoke-agriguard-operator-token-env.json`
  - Result: `passed=5, failed=0, total=5`

## Decision

Adopt the env-token alignment. Local browser smokes still work with dev fallback, and staging/real-token smokes can now be driven consistently by one environment variable.
