# AutoResearch Loop: Provider Preflight Docs URLs

Date: 2026-07-04

## Objective

Make the remaining DeSci external provider auth/config blocker more actionable
without weakening the fail-closed launch gate.

## Scope and Owned Paths

- `scripts/provider_preflight.py`
- `scripts/external_gate_handoff.py`
- `backend/tests/test_provider_preflight.py`
- `backend/tests/test_external_gate_handoff.py`

## A/B Hypothesis

- Baseline: provider preflight knew each check's provider docs URL, but the
  condensed `failed_checks` surface and handoff next actions did not preserve
  it.
- Variant: copy the secret-free `docs_url` into failed provider checks, carry
  it into provider handoff actions, roll it up per provider, and render it in
  Markdown next actions.
- Decision rule: adopt only if the current no-go provider state remains
  fail-closed, provider auth counts stay intact, focused tests pass, and live
  handoff evidence includes the expected Railway/Vercel docs URLs.

## Result

Adopted.

The live provider state is still correctly blocked by external auth/config:

- Railway: `railway whoami` and `railway status` fail with
  `auth_context_missing`; `railway variable --help` passes.
- Vercel: `vercel whoami` and `vercel env ls production` fail with
  `auth_context_missing`.
- GitHub: `gh auth status` and `gh secret list` pass.

The handoff now records docs URLs on provider-preflight next actions:

- Railway: `https://docs.railway.com/variables`
- Vercel: `https://vercel.com/docs/cli/env`

## Verification

- `python -m py_compile scripts\provider_preflight.py scripts\external_release_gate.py scripts\external_gate_handoff.py scripts\post_apply_evidence_gate.py`
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_external_gate_handoff.py -q` -> 59 passed.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q` -> 95 passed.
- `python scripts\provider_preflight.py --json-out var\provider-preflight-docs-url-2026-07-04.json --include-output-preview` -> expected exit 1; `missing_cli_count=0`, `auth_context_missing_count=4`.
- `python scripts\external_release_gate.py --json-out var\external-release-gate-provider-docs-url-2026-07-04.json` -> expected exit 1; `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `auth_context_missing=4`.
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-provider-docs-url-2026-07-04.json --json-out var\external-gate-handoff-provider-docs-url-2026-07-04.json --markdown-out var\external-gate-handoff-provider-docs-url-2026-07-04.md` -> expected exit 1; next actions include provider docs URLs.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-provider-docs-url-2026-07-04.json` -> 8 passed, 0 failed.
- Secret-shaped scan over generated docs-url evidence and this report -> no matches.

## Next Cycle

After operator auth/config is available, rerun the provider preflight, external
release gate, post-apply evidence gate, and browser launch-click suite before
promotion.
