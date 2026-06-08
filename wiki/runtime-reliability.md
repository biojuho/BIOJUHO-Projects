---
updated: 2026-06-08T15:54:18+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_rate_limits
    type: web
    title: OpenAI rate limits
    url: https://developers.openai.com/api/docs/guides/rate-limits
    checked: 2026-06-08
  - id: openai_error_codes
    type: web
    title: OpenAI error codes
    url: https://developers.openai.com/api/docs/guides/error-codes
    checked: 2026-06-08
  - id: openai_api_request_debugging
    type: web
    title: OpenAI API request debugging
    url: https://developers.openai.com/api/reference/overview
    checked: 2026-06-08
  - id: anthropic_rate_limits
    type: web
    title: Anthropic rate limits
    url: https://platform.claude.com/docs/en/api/rate-limits
    checked: 2026-06-08
  - id: anthropic_errors
    type: web
    title: Anthropic API errors
    url: https://platform.claude.com/docs/en/api/errors
    checked: 2026-06-08
  - id: anthropic_rate_limits_api
    type: web
    title: Anthropic Rate Limits API
    url: https://platform.claude.com/docs/en/manage-claude/rate-limits-api
    checked: 2026-06-08
  - id: google_gemini_rate_limits
    type: web
    title: Google Gemini API rate limits
    url: https://ai.google.dev/gemini-api/docs/rate-limits
    checked: 2026-06-08
  - id: google_gemini_troubleshooting
    type: web
    title: Google Gemini API troubleshooting
    url: https://ai.google.dev/gemini-api/docs/troubleshooting
    checked: 2026-06-08
  - id: vercel_ai_gateway_provider_options
    type: web
    title: Vercel AI Gateway provider options
    url: https://vercel.com/docs/ai-gateway/models-and-providers/provider-options
    checked: 2026-06-08
  - id: vercel_ai_gateway_provider_timeouts
    type: web
    title: Vercel AI Gateway provider timeouts
    url: https://vercel.com/docs/ai-gateway/models-and-providers/provider-timeouts
    checked: 2026-06-08
  - id: vercel_ai_gateway_fallbacks
    type: web
    title: Vercel AI Gateway model fallbacks
    url: https://vercel.com/docs/ai-gateway/models-and-providers/model-fallbacks
    checked: 2026-06-08
  - id: tail_at_scale
    type: paper
    title: "The Tail at Scale"
    url: https://research.google/pubs/the-tail-at-scale/
    checked: 2026-06-08
  - id: google_sre_book
    type: book
    title: "Site Reliability Engineering: How Google Runs Production Systems"
    url: https://openlibrary.org/books/OL27208603M
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - reliability
  - rate-limits
  - retries
  - latency
  - fallback
---

# Runtime Reliability

Runtime reliability covers the operational behavior of LLM routes under rate limits, transient API errors, slow responses, timeouts, streaming interruptions, overload, and fallback decisions.

## Runtime Contract

```js
const runtimePolicy = {
  route_id: "support_triage_agent",
  provider: "openai",
  model_route: "primary:gpt-5.5,fallback:gpt-5.4-mini",
  timeout_ms: 45000,
  stream_timeout_ms: 90000,
  max_retries: 2,
  retry_strategy: "jittered_exponential_backoff",
  retryable_errors: [429, 500, 502, 503, 504],
  idempotency_key_required: true,
  side_effect_tools_allowed_on_retry: false,
  circuit_breaker: "open_after_5_failures_per_60s",
  fallback_policy: "lower_cost_model|cached_answer|human_queue|fail_closed",
  slo: {
    success_rate: 0.995,
    p95_latency_ms: 12000,
    fallback_rate: 0.05,
    rate_limit_headroom: 0.2,
    error_budget_burn: "normal",
  },
  telemetry: ["x_request_id", "provider_latency_ms", "tokens", "cost", "retry_count"],
};
```

## Failure Classes

| Class | Symptom | Required control |
| --- | --- | --- |
| `rate_limit` | 429 or project/model/token quota pressure. | Backoff, queueing, lower concurrency, route-specific quotas. |
| `provider_server_error` | 5xx or overload error. | Bounded retry, circuit breaker, fallback route. |
| `timeout` | Request exceeds route timeout. | Token budget, streaming, chunking, smaller model or staged workflow. |
| `stream_interruption` | Stream starts but terminates before complete output. | Partial-output handling, resumable UI state, no blind replay for side effects. |
| `schema_parse_failure` | Structured output invalid or incomplete. | Small repair step before full retry. |
| `tool_timeout` | Tool call stalls or blocks run. | Tool timeout, cancellation, fallback, audit log. |
| `cost_spike` | Retry/fan-out amplifies token spend. | Per-run budgets and [[cost-observability]]. |
| `retry_side_effect_duplicate` | Agent repeats write action after retry. | Idempotency key and approval state persistence. |

OpenAI, Anthropic, Google Gemini, and Vercel expose enough headers and route controls that JooPark should not use blind retry loops. Provider constraints must feed a shared limiter and trace contract.

## Provider Surface

| Provider | Reliability surface | JooPark contract |
| --- | --- | --- |
| OpenAI | Rate limits are expressed across `RPM`, `RPD`, `TPM`, `TPD`, and `IPM`. Production logs should preserve `x-ratelimit-limit-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`, `x-request-id`, and `X-Client-Request-Id`. OpenAI recommends `random exponential backoff`, but warns that `unsuccessful requests contribute to your per-minute limit`. `503 - Slow Down` means reduce to the original request rate, stabilize, then ramp gradually. | Build a header-aware limiter; never retry indefinitely. |
| Anthropic | Claude rate limits use a `token bucket algorithm` and can return `retry-after`, `anthropic-ratelimit-requests-remaining`, `anthropic-ratelimit-requests-reset`, and `anthropic-ratelimit-input-tokens-reset`. Errors include `429 rate_limit_error`, `504 timeout_error`, `529 overloaded_error`, `request-id`, and `SSE after 200` error caveats. The `Rate Limits API` exposes `group_type`, `requests_per_minute`, `input_tokens_per_minute`, and `output_tokens_per_minute`. | Update client-side limiter state from response headers and admin API snapshots. |
| Google Gemini | Limits are `per project, not per API key`; `RPD quotas reset at midnight Pacific time`. `RPM`, `TPM`, `RPD`, `TPD`, and model-specific `IPM` vary by tier, and `experimental and preview models` can be more restricted. Troubleshooting separates `429 RESOURCE_EXHAUSTED`, `500 INTERNAL`, `503 UNAVAILABLE`, and `504 DEADLINE_EXCEEDED`. | Model route policy must include project-level quota and preview-model caveats. |
| Vercel AI Gateway | `providerOptions.gateway` supports provider `order`, `only`, fallback `models`, and `BYOK`. `providerTimeouts` are BYOK provider-start timeouts; timeout clears when the `first token arrives`. | Log provider route, fallback result, timeout metadata, and final served provider/model. |

## Runtime Policy Object

```js
const providerRuntimePolicy = {
  retryable_status: [429, 500, 503, 529],
  non_retryable_status: [400, 401, 403, 413],
  max_attempts: 4,
  backoff: "random_exponential_jitter",
  honor_retry_after: true,
  client_timeout_ms: 60000,
  providerOptions: {
    gateway: {
      order: ["anthropic", "openai", "google"],
      only: ["anthropic", "openai", "google"],
      models: ["openai/gpt-5.4", "anthropic/claude-sonnet-4.6"],
      providerTimeouts: { byok: { anthropic: 10000, openai: 15000 } },
    },
  },
  fallback_models: ["openai/gpt-5.4", "anthropic/claude-sonnet-4.6", "google/gemini-3-flash"],
  idempotency_key: "request_hash",
  x_client_request_id: "trace_id",
  trace_fields: ["fallback_reason", "served_model", "served_provider", "timeout_phase"],
};
```

## Source A/B Findings

| Comparison | A | B | JooPark decision |
| --- | --- | --- | --- |
| Rate-limit evidence | OpenAI response headers expose request/token limit, remaining, and reset data. | Anthropic combines response headers with a Rate Limits API for organization/workspace limit snapshots. | Use both: live headers for immediate throttling, admin snapshots for queue planning. |
| Error semantics | OpenAI distinguishes rate-limit, quota, overload, and `503 - Slow Down`. | Gemini and Anthropic expose typed 429/500/503/504/529 semantics with different retry rules. | Normalize errors into retryable/non-retryable classes, but keep raw provider code in traces. |
| Gateway routing | Single provider retry preserves model behavior. | Vercel provider `order`, `only`, `models`, and `providerTimeouts` support controlled failover. | Use gateway failover only after evals prove fallback quality and policy compatibility. |

## Retry Rules

- Retry only transient provider, network, and timeout errors.
- Do not retry side-effect tool calls unless the operation is idempotent and the idempotency key is preserved.
- Use bounded `random exponential backoff` and a max retry budget.
- If `retry-after` is present, `honor_retry_after` takes precedence over local backoff.
- Treat schema repair separately from full model replay.
- Log retry count, original request id, retry request ids, elapsed time, cost, `fallback_reason`, `served_model`, `served_provider`, and `timeout_phase`.
- Stop retries when the circuit breaker is open.
- Surface human-queue fallback when the route is important and fail-closed is safer than hallucinating.

## Fallback Matrix

| Fallback | Use when | Avoid when |
| --- | --- | --- |
| Smaller/faster model | Latency or cost pressure with low safety risk. | Domain quality or safety eval diverges. |
| Cached answer | User asks repeated stable question. | Answer depends on fresh or personal data. |
| RAG-only citation response | Model route is down but retrieval is healthy. | User needs synthesis or tool action. |
| Human queue | High-value workflow cannot safely degrade. | Low-stakes self-serve task. |
| Fail closed | Safety/privacy/tool permission uncertainty. | Product needs graceful read-only degradation. |

## Reliability Evals

| Eval | Checks |
| --- | --- |
| `rate_limit_backoff` | Route backs off and does not exceed max retries. |
| `timeout_budget` | Long prompt/tool path exits within route timeout. |
| `side_effect_retry_guard` | Write tool is not duplicated after provider failure. |
| `fallback_quality` | Fallback route produces acceptable output on representative tasks. |
| `tail_latency_budget` | p95/p99 stays within SLO for shadow/canary traffic. |
| `stream_recovery` | Partial stream does not create broken UI or duplicate tool calls. |

## A/B 비교: blind exponential retry vs header-aware client throttling

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Blind exponential retry | 구현이 쉽고 일시적 500/503에 빠르게 대응한다. | 429에서 실패 요청이 limit을 더 소모하고 herd effect가 생길 수 있다. | 낮은 QPS prototype. |
| B. Header-aware client throttling | `x-ratelimit-*`, `retry-after`, `anthropic-ratelimit-*`로 headroom을 계산해 실패 전 속도를 낮춘다. | shared quota state와 queue 운영이 필요하다. | production 기본값. |

## A/B 비교: single-provider retry vs cross-provider failover

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Single-provider retry | 품질, 정책, 로그가 일관되고 디버깅이 쉽다. | provider outage, quota exhaustion, regional issue에 취약하다. | strict compliance 또는 offline job. |
| B. Cross-provider failover | outage/rate-limit/capability mismatch에서 availability가 오른다. | fallback model quality drift, data policy 차이, cost variance, provider metadata 관측이 필요하다. | user-facing availability 우선 경로. |

## A/B 비교: long timeout vs fast failover timeout

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Long timeout | reasoning/large-context 요청이 끝날 가능성을 높인다. | 사용자가 오래 기다리고 worker slot을 점유한다. | 비동기 job, batch, non-interactive 분석. |
| B. Fast failover timeout | p95 latency와 UX를 안정화하고 느린 provider를 빨리 우회한다. | 취소 불가 provider에서는 과금될 수 있고 fallback 품질 검증이 필요하다. | latency-sensitive chat/tool path. |

## Product Hook

JooPark should show route-level reliability:

- current provider/model route and fallback state;
- p50/p95/p99 latency and timeout rate;
- 429/5xx/error-code distribution;
- retry count and retry cost;
- circuit breaker status;
- fallback decision and last successful baseline;
- side-effect retry guard status.

This belongs near [[rollout-decision-log]] because a route can pass offline evals and still fail production reliability.

## Open Questions

- Which routes should fail closed versus degrade to cached or human-queue behavior?
- Should each tool call have its own timeout budget inside the model route budget?
- What retry/cost ceiling should block a rollout even when answer quality is good?

## Backlinks

- [[index]]
- [[rollout-decision-log]]
- [[cost-observability]]
- [[agent-tool-permissions]]
- [[eval-result-lineage]]
- [[eval-failure-triage]]
- [[model-optimization-routing]]
- [[source-governance]]

## References

### Web

- OpenAI. "Rate limits." https://developers.openai.com/api/docs/guides/rate-limits
- OpenAI. "Error codes." https://developers.openai.com/api/docs/guides/error-codes
- OpenAI. "API request debugging." https://developers.openai.com/api/reference/overview
- Anthropic. "Rate limits." https://platform.claude.com/docs/en/api/rate-limits
- Anthropic. "Errors." https://platform.claude.com/docs/en/api/errors
- Anthropic. "Rate Limits API." https://platform.claude.com/docs/en/manage-claude/rate-limits-api
- Google. "Gemini API rate limits." https://ai.google.dev/gemini-api/docs/rate-limits
- Google. "Gemini API troubleshooting." https://ai.google.dev/gemini-api/docs/troubleshooting
- Vercel. "AI Gateway provider options." https://vercel.com/docs/ai-gateway/models-and-providers/provider-options
- Vercel. "AI Gateway provider timeouts." https://vercel.com/docs/ai-gateway/models-and-providers/provider-timeouts
- Vercel. "AI Gateway model fallbacks." https://vercel.com/docs/ai-gateway/models-and-providers/model-fallbacks

### Paper

- Dean and Barroso. "The Tail at Scale." Communications of the ACM, 2013. https://research.google/pubs/the-tail-at-scale/

### Book

- Beyer, Jones, Petoff, and Murphy. "Site Reliability Engineering: How Google Runs Production Systems." O'Reilly, 2016. ISBN 9781491929124. https://openlibrary.org/books/OL27208603M
