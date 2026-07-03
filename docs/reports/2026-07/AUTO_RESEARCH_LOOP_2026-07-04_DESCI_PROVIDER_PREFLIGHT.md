# AutoResearch Loop - DeSci Provider Preflight

Date: 2026-07-04 KST

## Objective

Add a secret-free provider CLI preflight so launch handoff can distinguish repo readiness from external provider setup blockers before applying Railway, Vercel, or GitHub secrets.

## Scope

- `apps/desci-platform/scripts/provider_preflight.py`
- `apps/desci-platform/backend/tests/test_provider_preflight.py`
- `apps/desci-platform/scripts/release_handoff.py`

## Source Checks

- Railway CLI and token guidance: https://docs.railway.com/cli
- Railway variables guidance: https://docs.railway.com/variables
- Vercel CLI env guidance: https://vercel.com/docs/cli/env
- Vercel environment variable guidance: https://vercel.com/docs/environment-variables
- GitHub secret CLI guidance: https://cli.github.com/manual/gh_secret_set
- GitHub auth status guidance: https://cli.github.com/manual/gh_auth_status

## A/B Decision

Option A: keep only the provider apply instructions in `release_handoff.py`.

Result: not enough. It tells the operator what to do, but does not create machine-readable evidence for whether the local provider CLI/auth context is ready.

Option B: add a non-mutating provider preflight that reuses the handoff command contract, suppresses secret output by default, records JSON evidence, and fails closed when provider auth/project context is not ready.

Result: adopted. The preflight gives the launch gate a repeatable provider readiness signal without writing provider secrets or dumping CLI stdout/stderr.

## Implementation Notes

- Added `scripts/provider_preflight.py` with provider-scoped checks for Railway, Vercel, and GitHub.
- Reused `release_handoff.provider_apply_guidance()` so handoff instructions and preflight checks share one provider contract.
- Removed `vercel link` from automatic preflight because it can mutate local project linkage. The handoff now keeps it as an explicit operator setup step.
- Added Windows npm shim handling so extensionless `railway`/`vercel` shims resolve to `.cmd` wrappers where needed.
- Added a Vercel auth-context guard. Without `VERCEL_TOKEN` or `~/.vercel/auth.json`, the script records `auth_context_missing` instead of launching an interactive CLI flow.
- Added timeout-safe, non-interactive CLI execution and default omission of stdout/stderr previews. Optional previews are sanitized before writing.

## Evidence

Provider preflight:

- Command: `python scripts/provider_preflight.py --timeout 12 --json-out var/provider-preflight-2026-07-04.json`
- Result: expected fail-closed provider state.
- Summary: providers 3, ready 1, checks 7, passed 3, failed 4, missing CLI 0, auth context missing 2.
- GitHub: OK (`gh auth status`, `gh secret list`).
- Railway: blocked by nonzero CLI readiness checks (`railway whoami`, `railway status`); `railway variable --help` is OK.
- Vercel: blocked by missing auth context (`vercel whoami`, `vercel env ls production`).
- Secret scan: no stdout/stderr previews and no secret-like substrings in `var/provider-preflight-2026-07-04.json`.

Regression checks:

- `python -m py_compile scripts/provider_preflight.py scripts/release_handoff.py` - pass.
- `python -m pytest backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py -q` - 42 passed.
- `python -m pytest backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` - 62 passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 15 --json-out var/browser-smoke-provider-preflight-2026-07-04.json --trace-on-failure-dir var/traces/provider-preflight-2026-07-04` - 9 passed, 0 failed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-preflight-2026-07-04.json` - 8 passed, 0 failed.

## Launch State

Local repo checks are green for this loop, but production launch remains no-go until external provider setup is completed:

- Railway CLI account/project/env readiness must pass.
- Vercel auth context and linked project/env readiness must pass.
- Browser readiness still reports no-go with launch blockers: auth, stripe, cors.
