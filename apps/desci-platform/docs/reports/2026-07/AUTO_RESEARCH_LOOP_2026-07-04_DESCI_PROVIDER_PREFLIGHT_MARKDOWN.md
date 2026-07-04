# AutoResearch Loop - DeSci Provider Preflight Markdown - 2026-07-04

## Objective

Make the DeSci provider preflight blocker state easier to review before public launch.

## Scope and Owned Paths

- `apps/desci-platform/scripts/provider_preflight.py`
- `apps/desci-platform/backend/tests/test_provider_preflight.py`

## Source Evidence

- Veritas AutoResearch source observed with `git ls-remote`:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Workspace modernization radar:
  - `github modernization radar valid: 8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline A: keep provider preflight as console output plus JSON only.
  - Rejected because release reviewers still need to parse JSON or console logs to identify exact Railway/Vercel unblock commands.
- Variant B: add `--markdown-out` and a sanitized Markdown renderer.
  - Adopted because it creates a human-readable artifact with the same provider counts, failed commands, docs URLs, and remediation text while keeping stdout/stderr previews out of Markdown.

## Implementation

- Added `render_markdown_report(...)` and `write_markdown_report(...)`.
- Added CLI flag `--markdown-out`.
- The Markdown report includes:
  - provider readiness counts
  - failed check counts
  - `missing_cli` and `auth_context_missing` counts
  - per-provider status
  - failed provider command, reason, docs URL, and remediation
- The renderer uses only structured/sanitized failed-check fields and does not render `stdout_preview`, `stderr_preview`, or raw command output.
- Test fixtures now compose fake secret-shaped strings at runtime so source scans stay clean while redaction behavior remains covered.

## Verification

- `python -m py_compile apps\desci-platform\scripts\provider_preflight.py apps\desci-platform\scripts\external_release_gate.py`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py -q`
  - Result: `12 passed in 0.34s`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py -q`
  - Result: `21 passed in 0.45s`
- `python scripts\provider_preflight.py --json-out var\provider-preflight-markdown-autoresearch-2026-07-04.json --markdown-out var\provider-preflight-markdown-autoresearch-2026-07-04.md --include-output-preview`
  - Expected exit: `1`
  - Result: `ok=False`, providers ready `1/3`, checks passed `3/7`, failed checks `4`, missing CLI `0`, auth context missing `4`
  - Blockers: `railway whoami`, `railway status`, `vercel whoami`, `vercel env ls production`
- Secret-shaped scan over changed source and generated provider artifacts: clean.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-provider-preflight-markdown-2026-07-04.json`
  - Result: `passed=8, failed=0, total=8`
- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\browser-smoke-launch-click-provider-preflight-markdown-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-provider-preflight-markdown-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-provider-preflight-markdown-2026-07-04-traces`
  - Result: browser launch-click suite passed.

## Current Launch Boundary

Local product and release-readiness checks remain green, but public launch is still blocked by external provider auth:

- Railway auth context missing for `railway whoami` and `railway status`.
- Vercel auth context missing for `vercel whoami` and `vercel env ls production`.
- GitHub provider preflight is currently OK.

## Next Cycle

After Railway/Vercel authentication is available, rerun provider preflight with both JSON and Markdown outputs, then rerun external release gate and post-apply evidence promotion.
