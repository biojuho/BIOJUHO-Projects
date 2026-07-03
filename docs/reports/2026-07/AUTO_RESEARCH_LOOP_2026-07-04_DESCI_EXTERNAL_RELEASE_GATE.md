# AutoResearch Loop - DeSci External Release Gate

Date: 2026-07-04 KST

## Objective

Move DeSci launch closer to production by combining offline deployment readiness and real provider CLI readiness into one machine-readable external release gate.

## Scope

- `apps/desci-platform/scripts/external_release_gate.py`
- `apps/desci-platform/backend/tests/test_external_release_gate.py`

Existing dirty files such as `apps/desci-platform/scripts/release_gate.py` were intentionally not staged or committed in this cycle.

## External Sources Checked

- GitHub deployment environments: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- GitHub deployment environment concepts: https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments
- env-doctor-cli: https://github.com/686f6c61/env-doctor-cli
- release-gate: https://github.com/VamsiSudhakaran1/release-gate
- atomic-agents doctor preflight issue: https://github.com/dep0we/atomic-agents-stack/issues/66
- Veritas AutoResearch source HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Decision

Option A: keep `deploy_readiness.py` and `provider_preflight.py` as separate operator commands.

Result: useful, but weak for launch handoff because it forces an operator or future agent to mentally join offline env failures with live provider auth failures.

Option B: add a small external release gate wrapper that runs both checks, preserves their full child payloads, and emits a single fail-closed JSON artifact.

Result: adopted. It improves launch evidence without touching dirty release-gate files or leaking provider command output.

## Implementation Notes

- Added `external_release_gate.py`.
- The wrapper normalizes `--target all` to Railway, Vercel, Amoy, and GitHub.
- Provider CLI preflight is run only for Railway, Vercel, and GitHub.
- Amoy-only runs record provider preflight as skipped instead of pretending a provider CLI check exists.
- Child payloads are preserved under `deploy_readiness` and `provider_preflight`.
- The top-level `failed_surfaces` list distinguishes offline deployment config blockers from provider CLI/auth blockers.

## Evidence

Focused checks:

- `python -m py_compile scripts/external_release_gate.py scripts/provider_preflight.py scripts/deploy_readiness.py` - pass.
- `python -m pytest backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py -q` - 48 passed.
- `python -m pytest backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` - 68 passed.

External release gate:

- Command: `python scripts/external_release_gate.py --provider-timeout 12 --json-out var/external-release-gate-provider-2026-07-04.json`
- Result: expected fail-closed.
- Summary: deploy failed 14, deploy warnings 3, provider ready 1/3, provider failed checks 4.
- Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Provider detail: GitHub ready; Railway `whoami/status` nonzero; Vercel auth context missing.
- Secret scan: no stdout/stderr previews and no secret-shaped values in the external gate JSON.
- Process cleanup: no leftover Railway/Vercel CLI processes.

Browser and workspace checks:

- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 15 --json-out var/browser-smoke-external-release-gate-2026-07-04.json --trace-on-failure-dir var/traces/external-release-gate-2026-07-04` - 9 passed, 0 failed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-external-release-gate-2026-07-04.json` - 8 passed, 0 failed.

## Current Launch State

The product remains no-go for public production launch. The local repo checks for this cycle are green, but the external release gate still reports missing production/provider setup:

- Offline deploy readiness: 14 failed, 3 warnings.
- Provider CLI readiness: GitHub OK, Railway and Vercel not ready.
- Browser launch control still reports blockers: auth, stripe, cors.

## Next Cycle

Use the external release gate artifact as the next operator handoff source. The highest-value next local improvement is to surface this combined external-gate result in the existing DeSci launch handoff/report flow without staging unrelated dirty release-gate changes.
