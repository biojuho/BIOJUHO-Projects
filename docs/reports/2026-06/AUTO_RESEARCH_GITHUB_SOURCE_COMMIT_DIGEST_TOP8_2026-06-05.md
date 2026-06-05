# AutoResearch GitHub Source Commit Digest Top 8

- Date: 2026-06-05
- Cycle status: adopted as source-selection evidence
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`

## Objective

Expand the live source-backed review loop beyond the top 4 repositories after
the first digest signals had already driven local hardening for hosted-agent
approval, Canva continuation handling, and OpenAI namespace metadata.

## A/B Contract

- Baseline: the checked-in commit digest selected only the top `4` pushed
  repositories from the review queue.
- Variant: run the same live digest over the top `8` pushed repositories and
  record a broader adoption/watch decision before changing product code.
- Primary KPI: identify the next highest-value local adoption candidate without
  broad or speculative code changes.
- Guardrails: no product code changes, no credentialed GitHub token required,
  and no adoption claim for repositories that returned no commit subjects.
- Decision rule: adopt the expanded digest only if it completes with `0`
  failed repositories and yields concrete next-cycle decisions.

## Result

- Expanded digest status: `pass`
- Selected repositories: `8`
- Failed repositories: `0`
- Token available: `false`
- Artifact JSON: `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_TOP8_2026-06-05.json`
- Artifact Markdown: `docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_TOP8_2026-06-05.md`

## Decisions

- `microsoft/agent-framework`: already converted into the hosted-agent approval boundary; keep monitoring CI/Copilot and ModelContextProtocol dependency signals.
- `mastra-ai/mastra`: continuation handling already converted into Canva MCP continuation guards; PubSub batching/signal-provider changes remain candidates only if a local event/subscriber surface is selected.
- `microsoft/playwright-mcp`: no commit subjects returned for the pushed_at window; no local adoption.
- `vercel/ai`: OpenAI function-call namespace signal already converted into Canva MCP OpenAI namespace metadata preservation; Vertex speech mode is unrelated to current launch surfaces.
- `OpenHands/OpenHands`: next review candidate. The Slack repo-inference and UTC timestamp fixes suggest checking local agent workflow evidence for async identity/timestamp assumptions before adopting anything.
- `pydantic/pydantic-ai`: next review candidate. Uploaded-file consistency and incomplete streamed-response handling may map to shared harness or event-stream guards, but require code inspection before adoption.
- `Significant-Gravitas/AutoGPT`: no commit subjects returned for the pushed_at window; no local adoption.
- `agno-agi/agno`: no commit subjects returned for the pushed_at window; no local adoption.

## Verification

- `python ops/scripts/github_source_commit_digest.py --top 8 --json-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_TOP8_2026-06-05.json --markdown-out docs/reports/2026-06/GITHUB_SOURCE_COMMIT_DIGEST_TOP8_2026-06-05.md`
  - Passed: `selected=8`, `failed=0`.

## Next Cycle

Review either `OpenHands/OpenHands` timestamp/async identity signals against
local agent workflow evidence, or `pydantic/pydantic-ai` uploaded-file and
streaming-response signals against the shared harness. Adopt only after a
specific local guardrail is identified.
