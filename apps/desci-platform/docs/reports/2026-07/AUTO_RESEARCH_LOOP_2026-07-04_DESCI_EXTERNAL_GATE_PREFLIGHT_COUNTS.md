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

- `scripts/external_gate_handoff.py`
  - Adds `provider_check_count`.
  - Adds `provider_missing_cli_count`.
  - Adds `provider_auth_context_missing_count`.
  - Renders those counts in Markdown and console output.
- `backend/tests/test_external_gate_handoff.py`
  - Covers JSON summary fields.
  - Covers Markdown and console count rendering.

## Verification

- `python -m py_compile scripts\external_gate_handoff.py`
  - Pass.
- `python -m pytest backend\tests\test_external_gate_handoff.py -q`
  - `51 passed`.
- `python scripts\external_gate_handoff.py --external-gate-json var\external-release-gate-provider-2026-07-04.json --json-out var\external-gate-handoff-provider-counts-2026-07-04.json --markdown-out var\external-gate-handoff-provider-counts-2026-07-04.md --provider-template-dir var\external-gate-provider-counts-2026-07-04 --provider-template-index-out var\external-gate-provider-counts-index-2026-07-04.json`
  - Expected exit code `1`: external gate remains no-go.
  - JSON summary includes `provider_check_count=7`,
    `provider_missing_cli_count=0`, and
    `provider_auth_context_missing_count=2`.
  - Console output includes `provider_checks=7`, `missing_cli=0`, and
    `auth_context_missing=2`.
  - Markdown includes provider total, missing CLI, and auth-context-missing
    check counts.
- Secret-shaped scan over generated handoff JSON/Markdown/provider templates:
  - No matches for live/test API keys, Stripe webhook markers, private-key
    headers, raw Postgres URLs, bearer tokens, Supabase secret markers, or raw
    Railway unauthorized stderr.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-external-gate-preflight-counts-cli-2026-07-04.json`
  - `8 passed`, `0 failed`.

## Artifacts

- `var\external-gate-handoff-provider-counts-2026-07-04.json`
- `var\external-gate-handoff-provider-counts-2026-07-04.md`
- `var\external-gate-provider-counts-index-2026-07-04.json`
- `var\external-gate-provider-counts-2026-07-04\amoy.env`
- `var\external-gate-provider-counts-2026-07-04\github.env`
- `var\external-gate-provider-counts-2026-07-04\railway.env`
- `var\external-gate-provider-counts-2026-07-04\vercel.env`
