# AutoResearch GitHub Source Commit Digest Batch Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `mastra-ai/mastra` commit `3b45ea950155`,
  `feat(core/events): opt-in batched delivery for PubSub subscribers (#16482)`.
- Source documentation signal: `mastra-ai/mastra` commit `b756ff19ef26`,
  `docs(reference/pubsub): document opt-in subscriber batching (#17586)`.
- Source links:
  - https://github.com/mastra-ai/mastra/commit/3b45ea95015557a6cb9d70dc5252af54ab1b78ac
  - https://github.com/mastra-ai/mastra/commit/b756ff19ef26da52c9a0d5e258343c1f53bc8394

## A/B Contract

- Baseline: `github_source_commit_digest.py` selected the top pushed-at source
  repositories and fetched commit subjects, but repositories beyond `--top`
  were not visible in the digest. Bursty upstream source movement could
  therefore be truncated without an explicit next-review queue.
- Variant: keep the existing top-N fetch behavior, but add a `selection_batch`
  section that records candidate count, selected count, overflow count,
  `overflow_policy`, and the unfetched overflow queue.
- Primary KPI: source bursts are coalesced into a visible review batch without
  increasing live GitHub fetch volume.
- Guardrails: no extra network requests; checked-in JSON and Markdown digest
  artifacts must match the renderer; overflow repositories are deferred rather
  than claimed reviewed.
- Decision rule: adopt only if digest tests, regenerated digest artifacts, and
  AutoResearch audits pass.

## Result

- Adopted variant: yes.
- `GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json` now records
  `selection_batch` with `candidate_repositories=13`,
  `selected_repositories=4`, and `overflow_repositories=9`.
- Overflow examples now visible for the next cycle include
  `OpenHands/OpenHands`, `pydantic/pydantic-ai`, `google/adk-python`,
  `evalstate/fast-agent`, and `Uninen/devserver-mcp`.
- `GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md` now includes a
  `Selection Batch` section and overflow table.

## Changed Paths

- `ops/scripts/github_source_commit_digest.py`
- `tests/test_github_source_commit_digest.py`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json`
- `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md`

## Verification

- `python -m pytest tests/test_github_source_commit_digest.py -q`
  - Passed: `6`.
- `python ops/scripts/github_source_commit_digest.py --json-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.json --markdown-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_2026-06-05.md`
  - Passed: selected `4`, failed `0`.

## Next Cycle

- Review the overflow queue before expanding the next live commit digest batch
  or adopting another local source-backed variant.
