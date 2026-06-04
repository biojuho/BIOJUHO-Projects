# AutoResearch GitHub Source Commit Digest

- Date: 2026-06-05
- Cycle status: adopted as source-review automation
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Primary sources:
  - https://github.com/microsoft/agent-framework
  - https://github.com/mastra-ai/mastra
  - https://github.com/microsoft/playwright-mcp
  - https://github.com/vercel/ai

## A/B Contract

- Baseline: `GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05` ranked `27/27`
  changed repositories but still required manual upstream commit review before
  any local adoption decision.
- Variant: add `ops/scripts/github_source_commit_digest.py` to fetch live
  commit subjects for the highest-ranked queued repositories with `pushed_at`
  movement.
- Primary KPI: the top source-review candidates become concrete commit
  windows with repository, commit count, subjects, source links, and an
  adoption decision.
- Guardrails: GitHub REST API quota failures must not be treated as missing
  source evidence when the public GitHub Atom feed can supply primary-source
  commit subjects; local product code must not change from commit subjects
  alone.
- Decision rule: adopt the digest automation only when it writes deterministic
  JSON/Markdown evidence, records fetch provenance, and keeps the broader
  objective open.

## Result

- Adopted variant: yes.
- Digest output: `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json`
  and `.md`.
- Selected repositories: `4/4`.
- Failed repositories: `0`.
- Token available: `false`.
- REST quota behavior: GitHub REST returned quota failures on this IP, so the
  script fell back to `github_atom_feed`.
- Adoption result: no local product-code adoption in this cycle; commit
  subjects are now a review input for the next A/B decision.

## Commit Review Summary

- `microsoft/agent-framework`: `4` commit subjects returned, including
  workflow/CI, ModelContextProtocol dependency, hosted-agent consent, and schema
  restructuring signals. Decision: `review_required_before_local_adoption`.
- `mastra-ai/mastra`: `5` commit subjects returned, including client tools,
  PubSub batching, signal abstractions, and OpenTelemetry dependency movement.
  Decision: `review_required_before_local_adoption`.
- `microsoft/playwright-mcp`: `0` default-branch Atom feed commits returned for
  the recorded `pushed_at` window, so there is no local adoption signal from
  that window. Decision: `no_local_adoption_commit_window_empty`.
- `vercel/ai`: `5` commit subjects returned, including canary versioning,
  Google Vertex speech mode, OpenAI function-call namespace handling, and
  contribution docs. Decision: `review_required_before_local_adoption`.

## Changed Paths

- `ops/scripts/github_source_commit_digest.py`
- `tests/test_github_source_commit_digest.py`
- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`
- `tests/test_autoresearch_completion_audit.py`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md`
- `docs/reports/2026-06/AUTO_RESEARCH_GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md`

## Verification

- `python ops/scripts/github_source_commit_digest.py --json-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json --markdown-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md --top 4 --max-commits 5`
  - Passed: `selected=4`, `failed=0`.
- `python -m pytest tests/test_github_source_commit_digest.py tests/test_github_source_review_queue.py tests/test_github_source_freshness.py tests/test_pre_push_hook.py tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - Passed: `44`.
- `python ops/scripts/autoresearch_completion_audit.py --json-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - Passed: `41` criteria, `global_objective_complete=false`.
- `python ops/scripts/autoresearch_objective_coverage.py --json-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - Passed: `7` requirements, `global_objective_complete=false`.

## Next Cycle

- Use the digest to choose one source-backed local experiment instead of
  broadly adopting upstream code. The strongest candidates are Agent Framework
  hosted-agent consent/workflow evidence, Mastra signal/PubSub resilience, and
  Vercel AI function-call namespace handling.
