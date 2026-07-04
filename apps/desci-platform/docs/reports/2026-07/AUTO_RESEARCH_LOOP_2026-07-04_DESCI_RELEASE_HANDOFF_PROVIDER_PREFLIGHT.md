# AutoResearch Loop - DeSci Release Handoff Provider Preflight

Date: 2026-07-04

## Goal

Make the release handoff distinguish unresolved provider secrets/configuration
from provider CLI/auth readiness, so operators can see whether the machine is
ready to apply Railway, Vercel, and GitHub changes.

## A/B Decision

- Baseline: `release_handoff.py` carried product smoke, deploy readiness, and
  release-gate consistency evidence, but omitted provider CLI preflight status.
- Variant: accept optional `--provider-preflight-json`, summarize provider CLI
  checks in the handoff JSON, and render a `## Provider CLI Preflight` section
  in the Markdown packet.
- Decision: keep the variant. It makes the handoff more actionable without
  copying command output previews or secret-like data into the operator packet.

## Changes

- `scripts/release_handoff.py`
  - Adds `provider_preflight_report(...)`.
  - Adds `provider_preflight_ok` and `provider_preflight` to JSON output when
    preflight evidence is supplied.
  - Adds `--provider-preflight-json`.
  - Renders provider CLI readiness, counts, and failed command reasons in
    Markdown.
- `backend/tests/test_deploy_readiness.py`
  - Covers JSON/Markdown provider-preflight output.
  - Covers the new CLI argument.

## Verification

- `python -m py_compile scripts\release_handoff.py`
  - Pass.
- `python -m pytest backend\tests\test_deploy_readiness.py -q`
  - `37 passed`.
- `python scripts\provider_preflight.py --json-out var\provider-preflight-current-2026-07-04.json --include-output-preview`
  - Expected fail-closed result.
  - GitHub OK.
  - Railway failed `railway whoami` and `railway status` with `nonzero_exit`.
  - Vercel failed `vercel whoami` and `vercel env ls production` with
    `auth_context_missing`.
- `python scripts\release_handoff.py --product-smoke-json var\desci-product-smoke-release-gate.json --deploy-readiness-json var\deploy-readiness-launch-handoff-current-2026-07-04.json --release-gate-json var\release-gate-launch-decision-strict-2026-07-04.json --provider-preflight-json var\provider-preflight-current-2026-07-04.json --json-out var\release-handoff-current-2026-07-04.json --markdown-out var\release-handoff-current-2026-07-04.md --env-template-out var\release-handoff-current-2026-07-04.env --provider-template-dir var\release-handoff-provider-templates-2026-07-04`
  - Expected exit code `1`: launch remains blocked by deploy readiness and
    provider preflight.
  - `provider_preflight_ok=false`.
  - `ready_provider_count=1`, `provider_count=3`.
  - `failed_check_count=4`.
  - `auth_context_missing_count=2`.
  - Markdown includes `## Provider CLI Preflight`.
- Secret-shaped scan over generated handoff JSON/Markdown/env templates:
  - No matches for live/test API keys, Stripe webhook markers, private-key
    headers, raw Postgres URLs, bearer tokens, Supabase secret markers, the
    local secret RPC fixture, or raw Railway unauthorized stderr.

## Artifacts

- `var\provider-preflight-current-2026-07-04.json`
- `var\release-handoff-current-2026-07-04.json`
- `var\release-handoff-current-2026-07-04.md`
- `var\release-handoff-current-2026-07-04.env`
- `var\release-handoff-provider-templates-2026-07-04\amoy.env`
- `var\release-handoff-provider-templates-2026-07-04\github.env`
- `var\release-handoff-provider-templates-2026-07-04\railway.env`
- `var\release-handoff-provider-templates-2026-07-04\vercel.env`
