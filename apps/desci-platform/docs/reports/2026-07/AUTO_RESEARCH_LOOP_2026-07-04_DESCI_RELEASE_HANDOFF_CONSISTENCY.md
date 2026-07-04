# AutoResearch Loop - DeSci Release Handoff Consistency

Date: 2026-07-04

## Goal

Carry the release-gate live-vs-browser consistency proof into the operator
release handoff, so the handoff shows both provider blockers and whether the
dashboard launch-control evidence matched the live API.

## A/B Decision

- Baseline: `release_handoff.py` merged product-smoke and deploy-readiness
  evidence, but did not include the parent release-gate action/decision
  comparison.
- Variant: accept optional `--release-gate-json`, summarize
  `launch_action_coverage_comparison` and `launch_decision_comparison`, and
  render that status in Markdown.
- Decision: keep the variant. It keeps the operator packet compact while
  proving that the no-go handoff is based on consistent live API and browser UI
  launch evidence.

## Changes

- `scripts/release_handoff.py`
  - Adds `release_gate_consistency_report(...)`.
  - Adds `release_gate_consistency_ok` and `release_gate_consistency` to JSON
    handoff payloads when a release-gate parent JSON is provided.
  - Adds a `## Release Gate Consistency` Markdown section.
  - Adds `--release-gate-json`.
- `backend/tests/test_deploy_readiness.py`
  - Covers JSON/Markdown consistency output.
  - Covers the new CLI argument.

## Verification

- `python -m py_compile scripts\release_handoff.py`
  - Pass.
- `python -m pytest backend\tests\test_deploy_readiness.py -q`
  - `36 passed`.
- `python scripts\deploy_readiness.py --target all --env-file .env.production --env-file contracts\.env --json-out var\deploy-readiness-launch-handoff-current-2026-07-04.json`
  - Expected fail-closed result: `16 failed`, `3 warning(s)`.
- `python scripts\release_handoff.py --product-smoke-json var\desci-product-smoke-release-gate.json --deploy-readiness-json var\deploy-readiness-launch-handoff-current-2026-07-04.json --release-gate-json var\release-gate-launch-decision-strict-2026-07-04.json --json-out var\release-handoff-current-2026-07-04.json --markdown-out var\release-handoff-current-2026-07-04.md --env-template-out var\release-handoff-current-2026-07-04.env --provider-template-dir var\release-handoff-provider-templates-2026-07-04`
  - Expected exit code `1`: deploy readiness is blocked.
  - Wrote JSON, Markdown, aggregate env template, and provider env templates.
  - `release_gate_consistency_ok=true`.
  - `action_coverage_status=match`.
  - `launch_decision_status=match`.
- Secret-shaped scan over generated handoff JSON/Markdown/env templates:
  - No matches for live/test API keys, Stripe webhook markers, private-key
    headers, raw Postgres URLs, bearer tokens, Supabase secret markers, or the
    local secret RPC fixture.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-release-handoff-consistency-2026-07-04.json`
  - First run timed out before result at the previous 180s command timeout.
  - Rerun with a longer command timeout passed: `passed=8`, `failed=0`,
    `total=8`.

## Artifacts

- `var\deploy-readiness-launch-handoff-current-2026-07-04.json`
- `var\release-handoff-current-2026-07-04.json`
- `var\release-handoff-current-2026-07-04.md`
- `var\release-handoff-current-2026-07-04.env`
- `var\release-handoff-provider-templates-2026-07-04\amoy.env`
- `var\release-handoff-provider-templates-2026-07-04\github.env`
- `var\release-handoff-provider-templates-2026-07-04\railway.env`
- `var\release-handoff-provider-templates-2026-07-04\vercel.env`
- `var\workspace-smoke-desci-release-handoff-consistency-2026-07-04.json`
