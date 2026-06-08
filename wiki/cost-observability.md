---
updated: 2026-06-08T16:02:15+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_cost_optimization
    type: web
    title: OpenAI cost optimization
    url: https://developers.openai.com/api/docs/guides/cost-optimization
    checked: 2026-06-08
  - id: openai_latency_optimization
    type: web
    title: OpenAI latency optimization
    url: https://developers.openai.com/api/docs/guides/latency-optimization
    checked: 2026-06-08
  - id: openai_prompt_caching
    type: web
    title: OpenAI prompt caching
    url: https://developers.openai.com/api/docs/guides/prompt-caching
    checked: 2026-06-08
  - id: openai_batch_api
    type: web
    title: OpenAI Batch API
    url: https://developers.openai.com/api/docs/guides/batch
    checked: 2026-06-08
  - id: openai_flex_processing
    type: web
    title: OpenAI Flex processing
    url: https://developers.openai.com/api/docs/guides/flex-processing
    checked: 2026-06-08
  - id: openai_priority_processing
    type: web
    title: OpenAI Priority processing
    url: https://developers.openai.com/api/docs/guides/priority-processing
    checked: 2026-06-08
  - id: anthropic_prompt_caching
    type: web
    title: Anthropic prompt caching
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
    checked: 2026-06-08
  - id: anthropic_batch_processing
    type: web
    title: Anthropic batch processing
    url: https://platform.claude.com/docs/en/build-with-claude/batch-processing
    checked: 2026-06-08
  - id: anthropic_token_counting
    type: web
    title: Anthropic token counting
    url: https://platform.claude.com/docs/en/build-with-claude/token-counting
    checked: 2026-06-08
  - id: openai_production_best_practices
    type: web
    title: OpenAI production best practices
    url: https://developers.openai.com/api/docs/guides/production-best-practices
    checked: 2026-06-08
  - id: openai_agents_tracing
    type: web
    title: OpenAI Agents SDK tracing
    url: https://openai.github.io/openai-agents-python/tracing/
    checked: 2026-06-08
  - id: openai_safety_checks
    type: web
    title: OpenAI safety checks
    url: https://developers.openai.com/api/docs/guides/safety-checks
    checked: 2026-06-08
  - id: langfuse_cost_tracking
    type: web
    title: Langfuse token and cost tracking
    url: https://langfuse.com/docs/observability/features/token-and-cost-tracking
    checked: 2026-06-08
  - id: frugalgpt
    type: paper
    title: "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance"
    url: https://arxiv.org/abs/2305.05176
    checked: 2026-06-08
  - id: dont_break_cache
    type: paper
    title: "Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks"
    url: https://arxiv.org/abs/2601.06007
    checked: 2026-06-08
  - id: cloud_finops
    type: book
    title: "Cloud FinOps"
    url: https://openlibrary.org/books/OL33774946M/Cloud_FinOps
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - cost
  - observability
  - tokens
  - latency
  - finops
---

# Cost Observability

Cost observability measures LLM spend in the same trace as quality, latency, retries, cache hits, route decisions, and user value. A cheap failed answer is not cheap; a costly answer that prevents escalation may be acceptable.

## Cost Trace Contract

```js
const llmCostTrace = {
  trace_id: "trace_...",
  route_id: "support_triage",
  model: "gpt-5.5",
  prompt_version: "support_triage_system@17",
  input_tokens: 4200,
  cached_input_tokens: 3100,
  output_tokens: 620,
  reasoning_tokens: 0,
  audio_tokens: 0,
  image_tokens: 0,
  retry_count: 1,
  batch_job_id: null,
  fallback_used: false,
  latency_ms: 8400,
  estimated_cost_usd: 0.021,
  success_metric: "grounded_answer_passed",
  user_value_unit: "resolved_ticket",
  cost_per_success_usd: 0.021,
};
```

Pricing values should live in a dated config, not be hardcoded in wiki text. Trace-level token and cost fields can be joined to current pricing when dashboards render.

## Cost Levers

- **fewer requests**: collapse unnecessary agent loops and move deterministic work outside the model.
- **minimize tokens**: trim prompts, retrieve fewer but better chunks, summarize history, cap output length.
- **smaller model**: use task-tiered routing and escalate only when the eval baseline requires it.
- **prompt caching**: record OpenAI `cached_tokens` and Anthropic `usage.cache_read_input_tokens` / cache creation tokens. Cache changes belong in [[prompt-release-management]].
- **Batch API / Message Batches API**: async low-priority work can use batch surfaces. OpenAI documents a 50% cost discount and 24-hour turnaround; Anthropic batch processing has similar async economics but is not Zero Data Retention (ZDR) eligible.
- **Flex/Priority**: `service_tier: "flex"` trades lower cost for slower response and more timeout handling. `service_tier: "priority"` trades premium token cost for lower, steadier latency.

Latency is also a cost signal. Track whether a route can process tokens faster, reduce output tokens, stream earlier, or use classical code instead of a model. User-facing paths should record `time_to_first_token` / `time_to_first_token_ms`.

```js
const costDecision = {
  service_tier: "flex|priority|default",
  cached_tokens: 3100,
  usage_cache_read_input_tokens: 2800,
  messages_count_tokens_preflight: "messages.count_tokens",
  batch_window: "24-hour turnaround",
  discount: "50% cost discount",
  tier_tradeoff: "premium token cost",
};
```

## Metrics

| Metric | Purpose |
| --- | --- |
| `cost_per_trace` | Basic spend per model call or agent run. |
| `cost_per_success` | Spend divided by accepted/eval-passing output. |
| `cached_token_ratio` | Prompt cache effectiveness and prompt-release stability. |
| `retry_cost_ratio` | Extra spend caused by retry or provider instability. |
| `fallback_cost_delta` | Cost/quality tradeoff from route fallback. |
| `batch_savings` | Difference between synchronous and batch processing. |
| `cost_latency_frontier` | Quality/cost/latency Pareto surface per route. |
| `cost_by_user_or_workspace` | FinOps allocation and abuse detection. |

OpenAI cost optimization docs point to prompt design, model choice, Batch, and flex processing. Prompt caching exposes `cached_tokens` in usage details, which should be stored at trace level. Langfuse cost tracking emphasizes ingesting token usage/cost from model responses when available.

## Observability Envelope

```js
const llmObservation = {
  trace_id: "trace_abc",
  span_id: "span_llm_001",
  parent_id: "span_route_001",
  workflow_name: "support_triage",
  group_id: "workspace_456",
  service_tier: "priority",
  cached_tokens: 3100,
  safety_identifier: "hash_user_123",
  time_to_first_token_ms: 740,
  spans: ["LLM generations", "function tool calls", "guardrails", "handoffs"],
  privacy_mode: "ZDR|standard|self-managed-redacted",
  route_stats: ["cost_per_success", "p50/p95/p99"],
};
```

OpenAI Agents SDK tracing covers LLM generations, function tool calls, guardrails, and handoffs. Provider tracing can be unavailable or inappropriate under ZDR or strict retention policies, so JooPark needs a self-managed OpenTelemetry/redacted trace option. Cost dashboards should show p50/p95/p99 latency beside spend; otherwise "cheap" routes can hide slow or failed work.

## Controls

- Per-route cost budget and per-run hard cap.
- Per-user/workspace monthly budget with alert thresholds.
- Retry budget tied to [[runtime-reliability]].
- Prompt cache hygiene tied to [[prompt-release-management]].
- Async Batch eligibility tied to [[model-optimization-routing]].
- High-cost trace sampling for reviewer inspection.
- Cost regression gate in [[rollout-decision-log]].

## Cost Evals

| Eval | Fails when |
| --- | --- |
| `cost_per_success_regression` | Candidate route costs more per accepted output than threshold. |
| `cache_hit_regression` | Prompt release breaks stable prefix and cache ratio drops. |
| `retry_spend_regression` | Reliability issue multiplies token spend. |
| `router_cost_quality` | Smaller route saves money but increases failure clusters. |
| `batch_eligibility` | Offline job runs synchronously despite batch-compatible SLA. |

## A/B 비교: async low-cost vs priority low-latency

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Batch/Flex 중심 | 낮은 단가, 대량 처리량, eval·embedding·분류에 적합하다. | 즉시성 없음, resource unavailable/timeout handling 필요. | 오프라인·비동기·재시도 가능한 작업. |
| B. Priority/streaming 중심 | 사용자 체감 latency와 일관성이 좋다. | premium token cost, ramp-rate와 service_tier fallback 관측 필요. | 결제·지원·실시간 생산성 같은 user-facing path. |

## A/B 비교: provider tracing vs self-managed OpenTelemetry

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Provider tracing | SDK 통합이 빠르고 LLM/tool/guardrail span이 자동 수집된다. | ZDR, 데이터 보존, 벤더 락인, cross-provider trace 결합 제약이 있다. | 단일 공급자·빠른 디버깅. |
| B. Self-managed OpenTelemetry | 기존 SRE stack과 연결하고 redaction/retention/PII 정책을 직접 통제한다. | span schema와 exporter 운영 부담이 있다. | 다중 공급자·규제 데이터·장기 운영. |

## Product Hook

JooPark should expose a cost observability panel:

- route and model spend by day;
- cost per successful answer;
- token mix, cached token ratio, retry ratio;
- latency and cost together;
- top expensive traces;
- budget alerts;
- prompt/model release that caused the change.

Cost dashboards should link to trace evidence. Aggregates without traces make regressions hard to explain.

## Open Questions

- What user value unit should JooPark use: successful answer, ticket resolved, task completed, or eval pass?
- Should cost budgets block rollouts automatically or require human approval?
- How should shared RAG/vector-store costs be allocated across routes?

## Backlinks

- [[index]]
- [[runtime-reliability]]
- [[model-optimization-routing]]
- [[prompt-release-management]]
- [[rollout-decision-log]]
- [[eval-result-lineage]]
- [[multimodal-file-inputs]]
- [[source-governance]]

## References

### Web

- OpenAI. "Cost optimization." https://developers.openai.com/api/docs/guides/cost-optimization
- OpenAI. "Latency optimization." https://developers.openai.com/api/docs/guides/latency-optimization
- OpenAI. "Prompt caching." https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI. "Batch API." https://developers.openai.com/api/docs/guides/batch
- OpenAI. "Flex processing." https://developers.openai.com/api/docs/guides/flex-processing
- OpenAI. "Priority processing." https://developers.openai.com/api/docs/guides/priority-processing
- OpenAI. "Production best practices." https://developers.openai.com/api/docs/guides/production-best-practices
- OpenAI Agents SDK. "Tracing." https://openai.github.io/openai-agents-python/tracing/
- OpenAI. "Safety checks." https://developers.openai.com/api/docs/guides/safety-checks
- Anthropic. "Prompt caching." https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic. "Batch processing." https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Anthropic. "Token counting." https://platform.claude.com/docs/en/build-with-claude/token-counting
- Langfuse. "Token & Cost Tracking." https://langfuse.com/docs/observability/features/token-and-cost-tracking

### Paper

- Chen et al. "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance." arXiv:2305.05176. https://arxiv.org/abs/2305.05176
- Kim et al. "Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks." arXiv:2601.06007. https://arxiv.org/abs/2601.06007

### Book

- Storment and Fuller. "Cloud FinOps." O'Reilly, 2020. ISBN 9781492054627. https://openlibrary.org/books/OL33774946M/Cloud_FinOps
