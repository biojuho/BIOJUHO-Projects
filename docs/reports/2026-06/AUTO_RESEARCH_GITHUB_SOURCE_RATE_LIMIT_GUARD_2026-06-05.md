# AutoResearch: GitHub Source Rate-Limit Guard

## Objective

Make GitHub source refresh failures caused by unauthenticated API limits explicit
and machine-readable, so a partial live artifact cannot be mistaken for a
complete source freshness snapshot.

## A/B Contract

- Baseline: `github_source_freshness.py` failed the run when repositories could
  not be fetched, but the report did not classify `403` API rate limits or mark
  the artifact as partial/token-required.
- Variant: classify GitHub API rate-limit failures as `github_api_rate_limit`,
  add report-level `complete`, `partial`, `rate_limited_count`,
  `token_required`, and `token_hint` fields, and support both `GITHUB_TOKEN` and
  `GH_TOKEN` for higher-volume live refreshes.
- Decision: adopted. The variant keeps the last complete `30/30` snapshot
  separate from a rate-limited live rerun and gives the operator an exact token
  boundary before a new snapshot can be adopted.

## Evidence

- `ops/scripts/github_source_freshness.py`
  - Adds `GitHubApiError` with per-repo `failure_type` and `requires_token`.
  - Classifies GitHub `403` or `429` rate-limit responses as
    `github_api_rate_limit`.
  - Emits `complete=false`, `partial=true`, `rate_limited_count`, and
    `token_required=true` when a partial live refresh hits the API quota.
  - Keeps pass/fail status strict: partial refreshes still return `status=fail`
    and cannot satisfy the complete snapshot criterion.
- `tests/test_github_source_freshness.py`
  - Simulates the observed `19/30` partial refresh pattern and asserts
    `rate_limited_count=11`, `partial=true`, and `token_required=true`.
  - Verifies Markdown includes `Rate-limited failures: `11`` and the
    `GITHUB_TOKEN or GH_TOKEN` operator hint.
  - Verifies `GH_TOKEN` is accepted as an authorization fallback.
- Prior live evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_READY_CREDENTIAL_LIVE_EXECUTION_2026-06-05.md`
  - The live verifier failed after `19/30` sources on unauthenticated GitHub API
    `403` rate-limit responses.
  - The partial live artifact was not adopted over the complete `30/30`
    snapshot.

## Verification

- `python -m pytest tests/test_github_source_freshness.py -q`
  - `7 passed`
- `python ops/scripts/autoresearch_completion_audit.py`
  - valid `25` criteria before contract registration
  - valid `26` criteria after contract registration
  - `global_objective_complete=false`
- `python ops/scripts/autoresearch_objective_coverage.py`
  - valid `7` requirements
  - `global_objective_complete=false`
- `python -m pytest tests/test_github_source_freshness.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `24 passed`
- `python -m pytest tests/test_github_source_freshness.py tests/test_external_credential_live_verify.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `30 passed`
- `python -m pytest tests/test_github_source_freshness.py tests/test_external_credential_live_verify.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `32 passed` after ready-only credential verifier integration
- `python -m pytest tests/test_github_source_freshness.py tests/test_external_credential_live_verify.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - `33 passed` after dry-run artifact drift guard integration

## Remaining Boundary

The next complete live source refresh can be adopted only after a successful
`30/30` run. If unauthenticated quota is exhausted, provide `GITHUB_TOKEN` or
`GH_TOKEN` and rerun:

```powershell
python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md
```
