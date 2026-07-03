# AutoResearch Loop - DeSci Browser/Auth/Skill Evidence - 2026-07-03

## Summary

- Objective: continue the AutoResearch/Karpathy loop for product-launch readiness, direct browser verification, source-backed modernization, and commit-ready self-improvement evidence.
- Outcome: adopted the better local variant for DeSci browser readiness after A/B verification.
- Product status: local DeSci quality gates and browser smoke are green; launch remains blocked only by external production configuration surfaced by `/ready` and `/launch`.
- Generated: `2026-07-03T20:20:00+09:00`

## Source-Backed Inputs

- GitHub modernization radar refreshed 8 repositories with live `git ls-remote` checks.
- Latest refresh result: checked=8, updated=6, failed=0, review_required=6.
- Current source queue:
  - `Veritas-7/autoresearch-skill-system`: updated to `b8bbf393759d6e67e780f03c572ec626fab6593b`.
  - `kodustech/agent-readiness`: updated to `6cb41fa749c0f601ec2803238e7d2e3b956f8076`.
  - `microsoft/agentrc`: reviewed for measure/generate/maintain agent workflow patterns.
  - `vercel/next-devtools-mcp`: reviewed for direct runtime/browser/log observability patterns.
  - `Uninen/devserver-mcp`: updated to `5f62b28d948d86a9ac1f803ecebf9926caa5cc77`.

Evidence files:

- `var/github-modernization-radar-auto-research.json`
- `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03.md`

## A/B Findings

### Baseline A: direct browser smoke before auth compatibility

- Command: `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --skip-login-validation --only-check home --only-check pricing --only-check explore --only-check login-dev-auth-redirect --expect-dev-auth --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-routes-auto-research.json`
- Result: failed.
- Failure: `/pricing` triggered `GET http://127.0.0.1:8000/subscription/tier` with HTTP 401.
- Diagnosis: frontend dev-auth bypass token was accepted by browser state but not by backend dev fallback.

### Variant B: backend accepts frontend dev-auth token only in non-production dev fallback

- Changed: `apps/desci-platform/backend/services/auth.py`
- Test added: `apps/desci-platform/backend/tests/test_auth.py`
- Result: adopted.
- Verification:
  - `uv run pytest tests/test_auth.py -q -p no:cacheprovider` -> 9 passed.
  - Route browser smoke after auth -> passed.

### Baseline C: full browser smoke after auth

- Command: `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --trace-on-failure-dir ..\var\desci-browser-traces --json-out ..\var\desci-browser-smoke-full-auto-research.json`
- Result: 56/57 passed.
- Failure: `vc-portal-select` reported no venture firm options.
- Diagnosis: backend `/vcs?limit=500` returned VC data; browser harness read the selector before async options finished rendering.

### Variant D: Playwright harness waits for current API and loaded VC options

- Changed: `apps/desci-platform/scripts/browser_smoke.py`
- Test added: `apps/desci-platform/backend/tests/test_browser_smoke.py`
- Result: adopted.
- Verification:
  - `uv run pytest tests/test_auth.py tests/test_browser_smoke.py -q -p no:cacheprovider` -> 41 passed.
  - `uv run pytest tests/test_auth.py tests/test_browser_smoke.py tests/test_vc_repository.py tests/test_vcs_router.py -q -p no:cacheprovider` -> 63 passed.
  - Single VC smoke -> passed.
  - Full browser smoke -> 57/57 passed.

## Final Verification

- AutoResearch skill validator: `.agents/skills/auto-research-karpathy/scripts/validate_skill.py` -> passed.
- AutoResearch/radar tests: `python -m pytest tests/test_auto_research_karpathy_skill.py tests/test_github_modernization_radar.py -q -p no:cacheprovider` -> 16 passed.
- Product smoke: `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --retries 2 --json-out ..\var\desci-product-smoke-auto-research-after-auth-rerun.json` -> passed.
- Browser route smoke after auth: `..\var\desci-browser-smoke-routes-auto-research-after-auth.json` -> passed.
- Browser dashboard smoke after auth: `..\var\desci-browser-smoke-dashboard-auto-research-after-auth.json` -> passed.
- Browser full smoke after VC wait: `..\var\desci-browser-smoke-full-auto-research-after-vc.json` -> 57/57 passed.
- Workspace DeSci smoke: `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-auto-research.json` -> 8/8 passed.

## Remaining Launch Blockers

These are not local browser/product regressions:

- `/ready` still reports blocked external launch configuration.
- `/launch` still returns no-go until production Stripe, Firebase/auth, Web3, and related deployment environment variables are configured.
- The current local release evidence supports continuing development and commit/push, not a production deploy without external operator secrets.

## Adopted Change Set

- AutoResearch skill and validation hardening:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `.agents/skills/auto-research-karpathy/references/source-backed-patterns.md`
  - `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
  - `.agents/skills/auto-research-karpathy/references/research-basis.md`
  - `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
- GitHub modernization radar:
  - `ops/references/github_modernization_sources.json`
  - `ops/scripts/github_modernization_radar.py`
  - `tests/test_auto_research_karpathy_skill.py`
  - `tests/test_github_modernization_radar.py`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03.md`
- DeSci browser/auth readiness:
  - `apps/desci-platform/backend/services/auth.py`
  - `apps/desci-platform/backend/tests/test_auth.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/desci-platform/backend/tests/test_browser_smoke.py`
