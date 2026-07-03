# AutoResearch Loop - DeSci Dashboard Launch Contract - 2026-07-03

## Summary

- Objective: continue direct browser verification after the previous AutoResearch push.
- Local hypothesis: the dashboard browser fixture should mirror the current `/ready` and `/launch` handoff contract instead of an older Stripe/Web3-only blocker profile.
- Outcome: adopted the contract-aligned fixture and kept full browser smoke green.
- Generated: `2026-07-03T20:45:00+09:00`

## A/B Finding

### Baseline A: older dashboard fixture

- Browser fixture blockers: `stripe`, `stripe_return_url`.
- Browser fixture next actions: `stripe`, `stripe_return_url`, `auth`, `stripe_portal`, `web3`.
- Current product smoke launch blockers: `auth`, `stripe`, `cors`.
- Current product smoke warning queue: `rabbitmq`, `ipfs`, `grobid`.
- Risk: dashboard browser smoke could pass while the fixture no longer represented the operator-facing launch blocker queue.

### Variant B: derive `/launch` fixture from `/ready` checks

- Changed: `apps/desci-platform/scripts/browser_smoke.py`
- Test updated: `apps/desci-platform/backend/tests/test_browser_smoke.py`
- Adopted because it improves drift resistance:
  - `/ready` fixture now uses the 13-check launch profile.
  - `/launch` fixture is computed from `/ready` checks instead of duplicating blocker/action lists.
  - Browser smoke now verifies `auth`, `stripe`, `cors`, `rabbitmq`, `ipfs`, and `grobid` action copy affordances.
  - Web3 triage remains covered through the readiness check details without incorrectly treating Web3 as the active local launch blocker.

## Verification

- `uv run pytest tests/test_browser_smoke.py -q -p no:cacheprovider` -> 33 passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-dashboard-contract-auto-research.json` -> passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-full-auto-research-dashboard-contract.json` -> 57/57 passed.
- `uv run pytest tests/test_browser_smoke.py tests/test_product_smoke.py tests/test_release_gate.py -q -p no:cacheprovider` -> 153 passed.
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --retries 2 --json-out ..\var\desci-product-smoke-auto-research-dashboard-contract.json` -> passed.

## Remaining Launch Boundary

- Local browser and smoke evidence is green.
- Production launch remains no-go until external operator configuration is supplied for Firebase/auth, Stripe, and production CORS origins.
- This loop improves local evidence fidelity; it does not claim external secrets are configured.
