# AutoResearch Loop - DeSci Provider Blocker Index - 2026-07-04

## Scope

Make the DeSci launch handoff bundle more actionable while the public launch remains blocked by provider preflight auth.

## Baseline

- The handoff refresh exposed provider preflight as counts only:
  - `provider_preflight=False`
  - `ready=1/3`
  - `failed=4`
  - `auth_missing=4`
  - `missing_cli=0`
- The underlying release handoff already had sanitized failed-check records, but the refresh bundle did not preserve them.

## Change

- `ops/scripts/desci_launch_handoff_refresh.py` now adds `release_handoff.provider_blockers`.
- Each blocker includes only:
  - `provider`
  - `id`
  - `command`
  - `failure_reason`
  - `remediation`
  - `docs_url`
- CLI stdout/stderr preview fields are intentionally omitted.
- `tests/test_desci_launch_handoff_refresh.py` now verifies the blocker index and confirms preview fields do not leak into the bundle.

## Verification

- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py`
- `python -m pytest tests\test_desci_launch_handoff_refresh.py -q`
  - Result: `13 passed in 2.26s`
- `python ops\scripts\desci_launch_handoff_refresh.py --live-source-commit b8bbf393759d6e67e780f03c572ec626fab6593b --check-live-source --allow-action-required --radar-json apps\desci-platform\var\github-modernization-radar-provider-blocker-index-2026-07-04.json --radar-markdown-out apps\desci-platform\docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_PROVIDER_BLOCKER_INDEX_2026-07-04.md --status-json-out apps\desci-platform\var\auto-research-status-desci-provider-blocker-index-2026-07-04.json --status-markdown-out apps\desci-platform\docs\reports\2026-07\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_PROVIDER_BLOCKER_INDEX_2026-07-04.md --secret-scan-json-out apps\desci-platform\var\desci-launch-secret-scan-provider-blocker-index-2026-07-04.json --bundle-json-out apps\desci-platform\var\desci-launch-handoff-refresh-provider-blocker-index-2026-07-04.json`
  - Result: `status=ok topic=DeSci live_source=current radar_auto_refreshed=True secret_scan=valid findings=0 missing=0 scanned=19 release_handoff=valid provider_preflight=False`
- `release_handoff.provider_blockers` in the generated bundle:
  - Count: `4`
  - Providers: `railway,vercel`
  - Reasons: `auth_context_missing`
- Secret-shaped pattern scan over the changed files and generated bundle: clean.
- Output-preview leak check over the generated bundle: no `stdout_preview`, `stderr_preview`, or `Unauthorized`.

## Current Launch Boundary

Public launch remains `no-go` until the operator authenticates/links provider CLIs or supplies equivalent provider tokens:

- Railway: `railway whoami`, `railway status`
- Vercel: `vercel whoami`, `vercel env ls production`
- GitHub provider preflight is not the current blocker in this run.
