---
updated: 2026-06-08T15:58:55+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_model_optimization
    type: web
    title: OpenAI model optimization
    url: https://developers.openai.com/api/docs/guides/model-optimization
    checked: 2026-06-08
  - id: openai_supervised_fine_tuning
    type: web
    title: OpenAI supervised fine-tuning
    url: https://developers.openai.com/api/docs/guides/supervised-fine-tuning
    checked: 2026-06-08
  - id: openai_external_models
    type: web
    title: OpenAI evaluate external models
    url: https://developers.openai.com/api/docs/guides/external-models
    checked: 2026-06-08
  - id: openai_evals
    type: web
    title: OpenAI evals
    url: https://developers.openai.com/api/docs/guides/evals
    checked: 2026-06-08
  - id: openai_eval_best_practices
    type: web
    title: OpenAI evaluation best practices
    url: https://developers.openai.com/api/docs/guides/evaluation-best-practices
    checked: 2026-06-08
  - id: anthropic_fine_tuning_glossary
    type: web
    title: Anthropic glossary fine-tuning
    url: https://platform.claude.com/docs/en/about-claude/glossary
    checked: 2026-06-08
  - id: google_gemini_model_tuning
    type: web
    title: Google Gemini model tuning
    url: https://ai.google.dev/gemini-api/docs/model-tuning
    checked: 2026-06-08
  - id: vercel_ai_gateway_fallbacks
    type: web
    title: Vercel AI Gateway model fallbacks
    url: https://vercel.com/docs/ai-gateway/models-and-providers/model-fallbacks
    checked: 2026-06-08
  - id: vercel_ai_gateway_observability
    type: web
    title: Vercel AI Gateway observability
    url: https://vercel.com/docs/ai-gateway/capabilities/observability
    checked: 2026-06-08
  - id: distillation_paper
    type: paper
    title: Distilling the Knowledge in a Neural Network
    url: https://arxiv.org/abs/1503.02531
    checked: 2026-06-08
  - id: frugalgpt
    type: paper
    title: "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance"
    url: https://arxiv.org/abs/2305.05176
    checked: 2026-06-08
  - id: unified_routing_cascading
    type: paper
    title: "A Unified Approach to Routing and Cascading for LLMs"
    url: https://arxiv.org/abs/2410.10347
    checked: 2026-06-08
  - id: ai_engineering
    type: book
    title: "AI Engineering: Building Applications with Foundation Models"
    url: https://openlibrary.org/books/OL54058212M/AI_Engineering
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - model-routing
  - optimization
  - cost
  - latency
  - distillation
---

# Model Optimization Routing

Model optimization routing decides whether a request should use prompt changes, RAG, a smaller model, a larger model, batch/flex processing, distillation, or a router/cascade. The decision must be measured against accuracy, safety, cost, latency, and availability.

## Routing Contract

```js
const modelRoute = {
  route_id: "support_triage",
  task_class: "grounded_qa|classification|summarization|tool_agent|creative|eval_batch",
  primary_model: "gpt-5.5",
  fallback_models: ["gpt-5.4-mini"],
  router_policy: "static|threshold|classifier|uncertainty|human",
  escalation_rule: "small_model_confidence_lt_0.72_or_safety_uncertain",
  optimization_target: "quality|latency|cost|availability|privacy",
  rag_required: true,
  batch_eligible: false,
  fine_tune_eligible: "unknown_checked_2026_06_08",
  eval_suite_ids: ["support-quality-v4", "safety-route-support-v3"],
  cost_budget_usd_per_1k: 4.5,
  p95_latency_budget_ms: 12000,
  rollback_route_id: "support_triage_20260601",
};
```

## Optimization Baseline

Optimization begins with an `eval baseline`; without it, a cheaper or faster route can hide regressions. For every candidate, store `eval_version`, `policy_version`, quality score, safety failures, `time_to_first_token`, cost, and latency.

## Decision Ladder

1. Improve prompt and structured output if failures are instruction or format issues.
2. Improve RAG if failures are missing, stale, or poorly ranked evidence.
3. Use a smaller/faster model if quality remains within eval threshold.
4. Use routing/cascade when task difficulty varies and escalation can be measured.
5. Use Batch API or async processing for non-interactive workloads.
6. Consider distillation or fine-tuning only when stable task/data/eval evidence justifies training overhead and platform availability is current.
7. Keep the larger model as fallback for safety, ambiguity, or high-value tasks.

OpenAI model optimization frames optimization as an eval-first loop and lists multiple tuning methods, but current fine-tuning availability is volatile. The source registry snapshot says the fine-tuning platform is winding down and not accessible to new users. If SFT is available for the org, OpenAI documents Supervised fine-tuning (SFT), Vision fine-tuning, Direct preference optimization (DPO), and Reinforcement fine-tuning (RFT). Anthropic's glossary states the Claude API does not currently offer fine-tuning. Google's Gemini tuning docs state the Gemini API or AI Studio no longer have a model available which supports fine-tuning after the Gemini 1.5 Flash-001 path changed. Treat all fine-tuning plans as `#검증필요` before product commitment.

## Provider Matrix

| Route lever | Provider evidence | JooPark use |
| --- | --- | --- |
| OpenAI SFT | Uses `purpose: "fine-tune"`, `POST /v1/fine_tuning/jobs`, `fineTuning.jobs.create`, `training_file`, `validation_file`, `suffix`, JSONL chat-completions, holdout data, `full_valid_loss`, and `full_valid_mean_token_accuracy`. Example target in docs/source registry: `gpt-4.1-mini-2025-04-14`. | Use only after eval baseline, data governance, and current availability check. |
| External model eval | OpenAI evals can compare native, third-party, and custom endpoints. External routes must document third-party terms and weaker safety guarantees. | Compare providers before routing traffic, not after outage pressure. |
| Gateway fallback | Vercel AI Gateway supports `providerOptions.gateway.models`; request logs expose provider metadata such as served route. | Trace `router_decision`, `fallback_reason`, `served_model`, `served_provider`, provider metadata, and route eval version. |
| Distillation | The distillation paper formalizes a teacher model and student model setup for compressing ensemble or larger-model behavior. | Use for high-volume stable tasks after filtering teacher errors and policy violations. |

```js
const sftCandidate = {
  training_file: "file_train123",
  validation_file: "file_valid123",
  suffix: "support-intent-v1",
  file_purpose: 'purpose: "fine-tune"',
  api_path: "POST /v1/fine_tuning/jobs",
  sdk_call: "fineTuning.jobs.create",
  format: "JSONL chat-completions",
  model: "gpt-4.1-mini-2025-04-14",
  metrics: ["full_valid_loss", "full_valid_mean_token_accuracy"],
};

const routingTrace = {
  router_decision: "small_model_then_gateway_fallback",
  fallback_reason: "provider_timeout",
  served_model: "anthropic/claude-sonnet-4.6",
  served_provider: "anthropic",
  provider_metadata: { source: "vercel-ai-gateway" },
  eval_version: "route-quality-v8",
  policy_version: "safe-comms-v5",
  time_to_first_token: 812,
};
```

## Optimization Matrix

| Technique | Best for | Avoid when | Evidence required |
| --- | --- | --- | --- |
| Prompt optimization | Instruction, tone, schema, citation behavior. | Missing knowledge or unstable policy. | [[prompt-release-management]] eval diff. |
| RAG improvement | Fresh or private knowledge, citation grounding. | Task is pure reasoning without docs. | [[rag-evals]] retrieval and answer metrics. |
| Smaller model | High-volume simple tasks. | Safety-critical or ambiguous tasks. | Accuracy/safety parity with production. |
| Larger model | Hard reasoning, synthesis, policy-sensitive decisions. | Low-value bulk jobs. | Error reduction justifies cost/latency. |
| Router/cascade | Mixed difficulty traffic. | No calibrated confidence or eval labels. | Per-class confusion, escalation rate, cost. |
| Batch/flex | Offline evals, enrichment, async jobs. | Interactive user flow. | Completion window and retry plan. |
| Distillation/fine-tune | Stable task with many examples and clear acceptance eval. | Data drift, privacy risk, platform uncertainty. | Training data governance and holdout eval. |

## Fine-Tuning Caveat

As of the 2026-06-08 source check, the source registry marks OpenAI fine-tuning availability with a "fine-tuning platform is winding down" caveat and "not accessible to new users." Anthropic says Claude API does not currently offer fine-tuning. Google says the Gemini API or AI Studio no longer have a model available which supports fine-tuning. Treat fine-tuning availability as volatile and recheck official docs before planning product work.

## Router Evals

| Eval | Checks |
| --- | --- |
| `route_quality_parity` | Candidate route meets quality threshold against current production. |
| `route_safety_parity` | Smaller/fallback route does not increase safety failures. |
| `escalation_precision` | Router sends hard/unsafe cases to stronger route. |
| `cost_per_success` | Cost reduction does not hide higher failure rate. |
| `latency_tail` | p95/p99 latency stays inside [[runtime-reliability]] budget. |
| `fallback_resilience` | Provider/model outage follows expected fallback behavior. |

## A/B 비교: fine-tuning vs RAG

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Fine-tuning/SFT | 반복 형식, 분류, 톤, instruction-following 실패를 낮은 latency로 개선할 수 있다. | availability 제한, dataset 품질·안전 리스크, 재학습 비용, 최신 지식 주입에는 부적합하다. | 고정된 behavior를 많은 요청에서 반복할 때. |
| B. RAG/prompt/tools | 최신·사내 지식 반영, 출처 인용, 데이터 갱신이 빠르다. | retrieval 품질, 인용 UX, context 비용 관리가 필요하다. | 지식/근거/권한이 핵심일 때 기본값. |

## A/B 비교: static routing matrix vs gateway fallback

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Static task-tiered routing matrix | eval과 비용을 명시적으로 통제하고 디버깅이 쉽다. | provider outage/rate limit 대응은 직접 구현해야 한다. | 안정된 workload, compliance가 중요한 경로. |
| B. Gateway fallback | provider outage, rate limit, capability mismatch에서 자동 failover 가능. | gateway lock-in, fallback quality drift, served model/provider 관측 필요. | availability 우선 user-facing path. |

## A/B 비교: teacher-student distillation vs runtime routing

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Teacher-student distillation | student model로 cost/latency를 줄이고 일관된 출력을 만들기 쉽다. | dataset 생성·검수·재학습이 필요하고 teacher model error를 고착시킬 수 있다. | 고빈도 고정 업무. |
| B. Runtime routing | 최신 frontier 능력을 필요할 때만 쓰고 task별 모델 교체가 빠르다. | 요청마다 latency/cost 변동, router eval, observability 부담이 있다. | 작업 난도가 넓고 빠르게 변할 때. |

## Product Hook

JooPark should expose a model route registry:

- task class and route owner;
- primary/fallback model;
- routing policy and escalation rule;
- eval suite and latest pass/fail;
- cost per successful answer;
- latency p95/p99;
- batch eligibility;
- fine-tune/distillation eligibility checked date.

## Open Questions

- Which JooPark routes are high-volume enough to justify a router?
- Should model routes be coupled to prompt versions or released independently?
- What quality drop is acceptable for a cheaper model on non-critical workflows?

## Backlinks

- [[index]]
- [[cost-observability]]
- [[runtime-reliability]]
- [[prompt-release-management]]
- [[rag-evals]]
- [[eval-dataset-governance]]
- [[rollout-decision-log]]
- [[data-privacy-retention]]
- [[source-governance]]

## References

### Web

- OpenAI. "Model optimization." https://developers.openai.com/api/docs/guides/model-optimization
- OpenAI. "Supervised fine-tuning." https://developers.openai.com/api/docs/guides/supervised-fine-tuning
- OpenAI. "Evaluate external models." https://developers.openai.com/api/docs/guides/external-models
- OpenAI. "Evals." https://developers.openai.com/api/docs/guides/evals
- OpenAI. "Evaluation best practices." https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Anthropic. "Glossary." https://platform.claude.com/docs/en/about-claude/glossary
- Google. "Gemini API model tuning." https://ai.google.dev/gemini-api/docs/model-tuning
- Vercel. "AI Gateway model fallbacks." https://vercel.com/docs/ai-gateway/models-and-providers/model-fallbacks
- Vercel. "AI Gateway observability." https://vercel.com/docs/ai-gateway/capabilities/observability

### Paper

- Chen et al. "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance." arXiv:2305.05176. https://arxiv.org/abs/2305.05176
- Šakota et al. "A Unified Approach to Routing and Cascading for LLMs." arXiv:2410.10347. https://arxiv.org/abs/2410.10347
- Hinton, Vinyals, and Dean. "Distilling the Knowledge in a Neural Network." arXiv:1503.02531. https://arxiv.org/abs/1503.02531

### Book

- Huyen. "AI Engineering: Building Applications with Foundation Models." O'Reilly, 2025. https://openlibrary.org/books/OL54058212M/AI_Engineering
