# AutoResearch Loop - DeSci Provider Apply Guidance

Date: 2026-07-04
App: apps/desci-platform
Branch: feat/shared-llm-modernization-2026-06-19

## Objective

Reduce the remaining DeSci launch no-go gap by turning provider-specific release blockers into operator-ready apply guidance inside the JSON and Markdown handoff.

## Scope and Owned Paths

- `apps/desci-platform/scripts/release_handoff.py`
- `apps/desci-platform/backend/tests/test_deploy_readiness.py`

Frontend files were not edited because the current worktree contains unrelated DeSci frontend changes. The real app click path was verified through browser smoke instead.

## External Sources Checked

- Railway variables and CLI docs: Railway variables are managed at service scope, can be pasted through the Variables RAW Editor, and CLI preflight uses authenticated project context.
- Vercel environment variable CLI docs: `vercel env add [name] [environment]`, `vercel env ls production`, and production variable changes require redeploy to affect new deployments.
- GitHub CLI secret docs: `gh secret set <KEY>` and `gh secret set -f .env` are supported repository-secret paths.
- AutoResearch source-backed loop rules: bounded A/B adoption, durable evidence, explicit staging, and push gates.

Sources:

- https://docs.railway.com/variables
- https://docs.railway.com/cli
- https://vercel.com/docs/cli/env
- https://vercel.com/docs/environment-variables
- https://cli.github.com/manual/gh_secret_set
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

## A/B Hypothesis

- A: Keep provider env templates and provider summary only.
- B: Add `apply_guidance` to each provider summary and render a `## Provider Apply Guidance` Markdown section with docs, preflight commands, and apply steps.

Decision: Adopt B. It makes the external launch blockers more actionable without storing or generating secrets.

## Implementation

- Added static provider guidance for Railway, Vercel, GitHub, Polygon Amoy, and product-only follow-up.
- Added `provider_apply_guidance()` and attached guidance to each provider summary.
- Rendered Markdown guidance under `## Provider Apply Guidance`.
- Extended release handoff tests for docs URLs and preflight command coverage.

## Generated Evidence

- `apps/desci-platform/var/desci-release-handoff-provider-apply-guidance-2026-07-04.json`
- `apps/desci-platform/var/desci-release-handoff-provider-apply-guidance-2026-07-04.env`
- `apps/desci-platform/var/desci-release-handoff-provider-apply-guidance-2026-07-04.md`
- `apps/desci-platform/var/desci-provider-apply-guidance-templates-2026-07-04/railway.env`
- `apps/desci-platform/var/desci-provider-apply-guidance-templates-2026-07-04/vercel.env`
- `apps/desci-platform/var/desci-provider-apply-guidance-templates-2026-07-04/github.env`
- `apps/desci-platform/var/browser-smoke-provider-apply-guidance-2026-07-04.json`
- `var/workspace-smoke-desci-provider-apply-guidance-2026-07-04.json`

Observed provider preflight:

- GitHub: `gh auth status`, `gh secret list`
- Railway: `railway whoami`, `railway status`, `railway variable --help`
- Vercel: `vercel whoami`, `vercel link`, `vercel env ls production`

## Verification

- `python -m py_compile apps/desci-platform/scripts/release_handoff.py` -> passed.
- `python -m pytest backend/tests/test_deploy_readiness.py -q` -> 35 passed.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 55 passed.
- `python scripts/release_handoff.py ... --provider-template-dir var/desci-provider-apply-guidance-templates-2026-07-04` -> no-go handoff generated as expected for blocked release evidence.
- Secret pattern scan across generated provider guidance artifacts -> no matches.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 15 --json-out var/browser-smoke-provider-apply-guidance-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-guidance-2026-07-04` -> 9/9 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-apply-guidance-2026-07-04.json` -> 8/8 passed.

## Current Launch State

Local code, release evidence generation, and browser click paths are green. Production launch remains no-go until external configuration is applied in Railway, Vercel, and GitHub, then the release handoff is regenerated against live provider state.

Next cycle should either add a provider status verifier that confirms CLI authentication/project binding without reading secrets, or expand browser coverage around Web3/governance flows.
