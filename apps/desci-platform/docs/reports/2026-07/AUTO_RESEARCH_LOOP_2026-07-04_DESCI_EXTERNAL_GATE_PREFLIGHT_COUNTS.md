# AutoResearch Loop - DeSci External Gate Preflight Counts

Date: 2026-07-04

## Goal

Make the tracked external-gate handoff summarize provider CLI preflight counts,
not just failed command names, so operators can distinguish missing CLI from
missing auth context in the provider workflow packet.

## A/B Decision

- Baseline: `external_gate_handoff.py` listed failed provider commands and
  reasons, but its top-level summary omitted total provider checks, missing CLI
  count, and auth-context-missing count.
- Variant: copy the sanitized counts from `provider_preflight.summary` into the
  external handoff summary and Markdown.
- Decision: keep the variant. It improves operator triage without copying raw
  command output or secret-shaped data.

## Changes

- `scripts/external_release_gate.py`
  - Adds provider preflight check, missing CLI, and auth-context-missing counts
    to the upstream external gate summary and console output.
- `scripts/external_gate_handoff.py`
  - Adds `provider_check_count`.
  - Adds `provider_missing_cli_count`.
  - Adds `provider_auth_context_missing_count`.
  - Renders those counts in Markdown and console output.
- `scripts/post_apply_evidence_gate.py`
  - Carries provider preflight counts into the post-apply promotion gate.
  - Fails closed if missing CLI or auth-context-missing counts are nonzero.
  - Renders those counts in console output.
- `backend/tests/test_external_gate_handoff.py`
  - Covers JSON summary fields.
  - Covers Markdown and console count rendering.
- `backend/tests/test_external_release_gate.py`
  - Covers upstream JSON summary fields.
  - Covers upstream console count rendering.
- `backend/tests/test_post_apply_evidence_gate.py`
  - Covers promotion-gate summaries, fail-closed provider auth counts, and
    console count rendering.

## Verification

- `python -m py_compile scripts\external_release_gate.py scripts\external_gate_handoff.py scripts\post_apply_evidence_gate.py`
  - Pass.
- `python -m pytest backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `87 passed`.
- `python scripts\external_release_gate.py --json-out var\external-release-gate-provider-counts-2026-07-04.json`
  - Expected exit code `1`: external gate remains no-go.
  - Console output includes `provider_checks=7`, `missing_cli=0`, and
    `auth_context_missing=2`.
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-provider-2026-07-04.json --json-out var\external-gate-handoff-provider-counts-2026-07-04.json --markdown-out var\external-gate-handoff-provider-counts-2026-07-04.md --provider-template-dir var\external-gate-provider-counts-2026-07-04 --provider-template-index-out var\external-gate-provider-counts-index-2026-07-04.json`
  - Expected exit code `1`: external gate remains no-go.
  - JSON summary includes `provider_check_count=7`,
    `provider_missing_cli_count=0`, and
    `provider_auth_context_missing_count=2`.
  - Console output includes `provider_checks=7`, `missing_cli=0`, and
    `auth_context_missing=2`.
  - Markdown includes provider total, missing CLI, and auth-context-missing
    check counts.
- `python scripts\post_apply_evidence_gate.py --external-gate-json var\external-release-gate-provider-counts-2026-07-04.json --json-out var\post-apply-evidence-gate-provider-counts-2026-07-04.json`
  - Expected exit code `1`: post-apply promotion remains blocked.
  - JSON summary includes `provider_check_count=7`,
    `provider_missing_cli_count=0`, and
    `provider_auth_context_missing_count=2`.
  - Console output includes `provider_checks=7`, `missing_cli=0`, and
    `auth_context_missing=2`.
  - Failure list includes `summary.provider_auth_context_missing_count must be 0`.
- Secret-shaped scan over generated handoff JSON/Markdown/provider templates:
  - No matches for live/test API keys, Stripe webhook markers, private-key
    headers, raw Postgres URLs, bearer tokens, Supabase secret markers, or raw
    Railway unauthorized stderr.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-post-apply-preflight-counts-2026-07-04.json`
  - `8 passed`, `0 failed`.
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 30 --json-out var\browser-smoke-launch-click-provider-preflight-counts-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-provider-preflight-counts-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-provider-preflight-counts-2026-07-04-traces`
  - `9 passed`, `0 failed`.
  - Covered landing CTA, explore analyze intent, pricing enterprise contact,
    dashboard quick upload, dashboard readiness refresh, mocked checkout,
    upload form readiness, upload submit receipt, and asset upload readiness.
  - Screenshots were written for all 9 checks.

## Artifacts

- `var\external-release-gate-provider-counts-2026-07-04.json`
- `var\external-gate-handoff-provider-counts-2026-07-04.json`
- `var\external-gate-handoff-provider-counts-2026-07-04.md`
- `var\post-apply-evidence-gate-provider-counts-2026-07-04.json`
- `var\browser-smoke-launch-click-provider-preflight-counts-2026-07-04.json`
- `var\browser-smoke-launch-click-provider-preflight-counts-2026-07-04-screens\*.png`
- `var\external-gate-provider-counts-index-2026-07-04.json`
- `var\external-gate-provider-counts-2026-07-04\amoy.env`
- `var\external-gate-provider-counts-2026-07-04\github.env`
- `var\external-gate-provider-counts-2026-07-04\railway.env`
- `var\external-gate-provider-counts-2026-07-04\vercel.env`
