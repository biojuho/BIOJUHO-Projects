# Dashboard Operator Browser Text Guard

- Date: 2026-06-05
- Scope: manifest-backed dashboard browser smoke regression guard
- Baseline: the dashboard operator checklist text was covered by live browser smoke evidence, but the pre-push test only validated generic expected-text behavior and route counts.
- Variant: add a focused manifest test that requires the dashboard home route to keep the operator checklist expected text.
- Primary KPI: accidental removal of the dashboard operator checklist browser assertions fails the pre-push pytest bundle before a future commit can be pushed.
- Guardrails: no live browser server is required for this guard, and the existing browser smoke runner remains the source for live route proof.

## Adopted Variant

Adopted. `tests/test_dev_server_browser_smoke.py` now includes `test_dashboard_operator_checklist_text_is_manifest_guarded`, which requires these dashboard home-route expected text strings:

- `CREDENTIAL OPERATOR CHECKLIST`
- `1 ready / 4 blocked`
- `Checklist next`
- `Required env: missing`
- `Canva OAuth and OpenAPI tool execution`

## Changed Paths

- `tests/test_dev_server_browser_smoke.py`

## Verification

- `python -m pytest tests\test_dev_server_browser_smoke.py -q` -> `8 passed`
- `git push origin HEAD:feat/observability-gateway-2026-05` for commit `e53d825` -> pre-push pytest bundle `145 passed`, credential handoff check passed, live-verifier dry-run passed, Telegram dry-run passed, objective coverage passed, MCP runtime smoke passed, MCP service runtime smoke passed, workflow gate probes passed, completion audit passed

## Remaining Boundary

This strengthens local regression protection for the dashboard operator checklist browser smoke manifest. It does not complete credential-gated Canva OAuth/OpenAPI execution, GitHub high-volume live refresh with a token, Telegram delivery, OTLP collector shipping, or hosted runtime/tracing operator decisions.

global_objective_complete=false
