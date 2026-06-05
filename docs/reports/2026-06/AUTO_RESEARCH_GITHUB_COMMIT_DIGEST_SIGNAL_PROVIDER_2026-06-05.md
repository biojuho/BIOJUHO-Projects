# AutoResearch GitHub Commit Digest Signal Provider

- Date: 2026-06-05
- Source reviewed: `mastra-ai/mastra` commit `e9be4e747ec3d8b65548bff92f9377db06105376`
- Source signal: `feat(core): add SignalProvider abstraction + @mastra/github-signals package (#17577)`
- Source URL: https://github.com/mastra-ai/mastra/commit/e9be4e747ec3d8b65548bff92f9377db06105376
- Local guard: `github_commit_digest_signal_provider_guard`
- Local provider: `github_commit_delta`
- Decision: adopted
- Marker: `global_objective_complete=false`

## A/B Contract

- A, control: keep `selection_batch.source_signal` as a static historical string.
- B, adopted: derive source-signal metadata from the selected GitHub commit delta, preferring `SignalProvider` or `github-signals` commit subjects when present, and render provider, repo, SHA, fetch source, and source URL in the digest.

## Adopted Changes

- `ops/scripts/github_source_commit_digest.py` now builds structured `selection_batch` metadata through `_source_signal_metadata()`.
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json` now records `source_signal_provider`, `source_signal_repo`, `source_signal_sha`, `source_signal_subject`, `source_signal_fetch_source`, and `source_signal_url`.
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md` now renders the same fields in the Selection Batch section.
- `tests/test_github_source_commit_digest.py` covers the SignalProvider selection path and checked-in renderer drift.

## Verification

- Focused digest/audit suite: `29 passed`.
- GitHub source commit digest proof: `selected=4`, `failed=0`.
- Workspace smoke: `6/6 passed` via `var/workspace-smoke-github-digest-signal-provider-2026-06-05.json`.
- Completion audit: `80 criteria`, `cycle_evidence_ready=true`, `global_objective_complete=false`.
- Objective coverage audit: `7 requirements`, `cycle_prompt_covered=true`, `global_objective_complete=false`.
