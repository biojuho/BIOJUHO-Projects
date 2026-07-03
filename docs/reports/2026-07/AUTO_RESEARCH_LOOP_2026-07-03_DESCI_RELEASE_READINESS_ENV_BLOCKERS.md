# AutoResearch Loop - DeSci Release Readiness Env Blockers

Date: 2026-07-03
Scope: `apps/desci-platform` runtime launch readiness after investor-directory hardening
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-hardening with source-backed AutoResearch. The previous cycle made
the public investor directory resilient to empty VC sync results and pushed
`f847150 fix: keep investor directory populated on VC sync gaps`. This cycle
checks whether the broader DeSci product can be called launch-ready from live
runtime evidence, not only from unit tests.

## External Sources Checked

- `lastmile-ai/mcp-eval`: real environment testing, traces, metrics, and
  integration assertions over mock-only confidence.
- `Uninen/devserver-mcp`: dev server status/log visibility and browser
  automation as first-class validation.
- `Veritas-7/autoresearch-skill-system`: bounded continuous improvement with
  same-sample A/B checks, durable archives, stop controls, and fail-closed
  completion audits.

Latest observed `Veritas-7/autoresearch-skill-system` main:

```text
b8bbf393759d6e67e780f03c572ec626fab6593b
```

The refreshed modernization radar was written to:

- `var/github-modernization-radar-release-readiness-2026-07-03.json`
- `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_RELEASE_READINESS_2026-07-03.md`

## A/B Contract

Baseline:

- Current live local runtime at `http://127.0.0.1:8000`
- Current dev-auth frontend at `http://127.0.0.1:5173`
- Existing post-commit evidence from investor-directory cycle

Variant:

- No code adoption in this cycle. A local readiness mismatch candidate was
  considered but rejected because the authoritative files already have large
  pre-existing dirty diffs, and staging a narrow hunk would risk mixing
  unrelated work.

Primary KPI:

- Live launch readiness should only be called ready when `/ready`, `/launch`,
  product smoke, browser smoke, and workspace smoke agree.

Decision rule:

- Adopt code only if a candidate removes a false positive without weakening
  production guardrails and can be staged without unrelated dirty hunks.
- Otherwise, record the blocker classification and keep release status
  fail-closed.

## Evidence

Accepted green local evidence:

- `var/workspace-smoke-desci-after-investors-2026-07-03.json`
  - `status=complete`
  - `passed=8`
  - `failed=0`
- `apps/desci-platform/var/browser-smoke-dev-auth-after-investors-2026-07-03.json`
  - full dev-auth browser smoke OK
- `apps/desci-platform/var/browser-smoke-pricing-anonymous-no-dev-auth-2026-07-03.json`
  - anonymous pricing redirect OK on a no-dev-auth temporary frontend
- `apps/desci-platform/var/browser-smoke-investors-fallback-2026-07-03.json`
  - investor filter and seed-directory fallback OK

Strict launch-readiness evidence:

- `var/desci-product-smoke-strict-ready-2026-07-03.json`
  - `ok=false`
  - `/ready status=blocked`
  - `/launch release_decision=no-go`
  - blockers: `auth`, `stripe`, `cors`

The strict blocker set is consistent with current runtime configuration:

- `auth`: no `GOOGLE_APPLICATION_CREDENTIALS` or complete
  `FIREBASE_SERVICE_ACCOUNT_JSON` is present for launch readiness.
- `stripe`: paid checkout launch vars are missing:
  `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`.
- `cors`: launch readiness requires deployed public HTTPS frontend origins,
  not localhost origins.

## Decision

Rejected code adoption for this cycle.

Reason: the strict launch blockers are environment and deployment readiness
blockers, not an application regression. Browser and workspace evidence prove
the local product paths are currently green, while strict product smoke
correctly remains no-go until production auth, Stripe, and deployed CORS
variables are configured.

The product should stay fail-closed for public launch.

## Verification Commands

```powershell
git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main
python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-release-readiness-2026-07-03.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_RELEASE_READINESS_2026-07-03.md
python apps/desci-platform/scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --timeout 10 --strict-ready --json-out var/desci-product-smoke-strict-ready-2026-07-03.json
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-after-investors-2026-07-03.json
```

## Next Cycle

Next high-value loop: choose a clean owned surface that improves release
operator handoff without weakening launch blockers. Good candidates are:

- a release handoff generator/summary that links green local evidence to the
  exact external production env variables still required, or
- a browser smoke preflight that refuses to run anonymous-only checks against a
  dev-auth frontend unless `--expect-dev-auth` is set.
