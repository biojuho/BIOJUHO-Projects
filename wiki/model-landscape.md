---
updated: 2026-06-08T16:03:57+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_models
    type: web
    title: OpenAI model comparison
    url: https://developers.openai.com/api/docs/models/compare
    checked: 2026-06-08
  - id: openai_api_platform
    type: web
    title: OpenAI API platform
    url: https://openai.com/api/
    checked: 2026-06-08
  - id: anthropic_models
    type: web
    title: Anthropic Claude models overview
    url: https://platform.claude.com/docs/en/about-claude/models/overview
    checked: 2026-06-08
  - id: google_gemini_models
    type: web
    title: Gemini API models
    url: https://ai.google.dev/gemini-api/docs/models
    checked: 2026-06-08
  - id: google_gemini_pricing
    type: web
    title: Google Gemini Developer API pricing
    url: https://ai.google.dev/gemini-api/docs/pricing
    checked: 2026-06-08
  - id: meta_llama4
    type: web
    title: Meta Llama 4 release
    url: https://ai.meta.com/blog/llama-4-multimodal-intelligence/
    checked: 2026-06-08
  - id: deepseek_pricing
    type: web
    title: DeepSeek API models and pricing
    url: https://api-docs.deepseek.com/quick_start/pricing
    checked: 2026-06-08
  - id: mistral_models
    type: web
    title: Mistral AI models overview
    url: https://docs.mistral.ai/models/overview
    checked: 2026-06-08
  - id: helm
    type: paper
    title: "Holistic Evaluation of Language Models"
    url: https://arxiv.org/abs/2211.09110
    checked: 2026-06-08
  - id: ai_engineering
    type: book
    title: "AI Engineering: Building Applications with Foundation Models"
    url: https://openlibrary.org/books/OL54058212M/AI_Engineering
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - models
  - landscape
  - registry
  - provider
---

# Model Landscape

Model landscape is the registry of model providers, model ids, capabilities, lifecycle state, and suitability for JooPark routes. It must be refreshed from official sources because model names, pricing, context windows, tool support, and deprecations change frequently.

## Registry Contract

```js
const modelRegistryEntry = {
  provider: "openai",
  model_id: "gpt-5.5",
  alias_or_snapshot: "snapshot|alias|preview|deprecated",
  checked_at: "2026-06-08",
  official_source_url: "https://developers.openai.com/api/docs/models/compare",
  modalities: ["text_in", "image_in", "text_out"],
  context_window_tokens: 1000000,
  max_output_tokens: 128000,
  tool_support: ["function_calling", "web_search", "file_search", "computer_use"],
  reasoning_control: "none|low|medium|high|xhigh",
  knowledge_cutoff: "2025-12-01",
  pricing_config_id: "pricing-openai-20260608",
  deprecation_status: "active|preview|legacy|deprecated|sunsetting",
  route_fit: ["complex_reasoning", "coding", "agentic_workflow"],
};
```

This registry should not duplicate complete provider docs. It stores the fields JooPark needs for routing, release decisions, and stale-source detection.

## 2026 Official Source Snapshot

| Row | Official source checked 2026-06-08 | Registry marker | JooPark caveat |
| --- | --- | --- | --- |
| OpenAI GPT-5.5 / GPT-5.4 | OpenAI API platform and model comparison list GPT-5.5, GPT-5.4, GPT-5.4 mini with context, max output, and pricing summary. | `GPT-5.5`, `GPT-5.4`, `GPT-5.4 mini` | Treat aliases and snapshots separately in [[prompt-release-management]]. |
| Google Gemini | Gemini model docs and Developer API pricing expose model capability rows and tiered pricing. | `Gemini 3.1 Pro Preview` | Pricing is tiered; do not average prompt tiers into one unit price. |
| DeepSeek | API model list currently includes `deepseek-v4-flash` and `deepseek-v4-pro`; pricing pages can differ by endpoint/version. | `DeepSeek V4 Flash` | #검증필요: confirm price, cache hit/miss, context, and output limits from official page before budget use. |
| Meta Llama | Meta Llama 4 release describes Llama 4 Scout/Maverick and open-weight availability. | `Llama 4 Scout` | Open-weight/partner/self-hosted cost is not equivalent to direct hosted API pricing. |

## Task-Tiered Model Matrix

| Route tier | Candidate rows | Routing default | Evidence required |
| --- | --- | --- | --- |
| High-stakes reasoning/coding | GPT-5.5, Claude Opus/Sonnet class, Gemini Pro preview class | Strong model first, no silent downgrade | safety eval, route quality eval, rollout decision. |
| High-volume routine work | GPT-5.4 mini / cheaper provider route / DeepSeek V4 Flash candidate | Smaller model first, escalate on uncertainty | cost_per_success, failure clusters, router_decision trace. |
| Ultra-long context | Llama 4 Scout candidate, Gemini long context candidate, OpenAI long context rows | Use only when citation quality and latency pass | context-window eval and cost/latency proof. |
| Open-weight/private route | Llama/open-weight family | self-host/partner evaluation | privacy, infrastructure cost, model ops capacity. |

This is a task-tiered model matrix, not a leaderboard. A model enters production only through [[model-optimization-routing]], [[cost-observability]], [[runtime-reliability]], and [[rollout-decision-log]].

## Source Snapshot

| Provider | Official source checked 2026-06-08 | Snapshot takeaway |
| --- | --- | --- |
| OpenAI | Model comparison + API platform | Docs list `GPT-5.5` as flagship for complex reasoning/coding, smaller variants for cost/latency, and current latest models with text/image input and tool support. |
| Anthropic | Claude models overview | Docs compare Claude Opus 4.8, Sonnet 4.6, and Haiku 4.5 with model ids, context/output limits, pricing, and provider deployment surfaces. |
| Google Gemini | Gemini API models + pricing | Docs expose model capability metadata, including supported modalities, token limits, function calling, structured outputs, search grounding, batch, caching, thinking, and tiered pricing. |
| Mistral | Mistral models overview | Docs list frontier, open, coding, moderation, OCR, audio, and document-related models with versioned model families. |
| Meta Llama | Llama 4 release | Llama 4 Scout is an open-weight/partner/self-hosted candidate; do not mix partner/self-hosted economics with API token prices. |
| DeepSeek | API model list + pricing | DeepSeek V4 Flash/Pro model IDs appear in the model-list endpoint; pricing/context rows must be rechecked because official pages may differ by endpoint. |

Only official sources should update the registry. Blog posts, dashboards, and third-party leaderboards can suggest candidates but should not promote a model to production without official capability and pricing checks.

## Selection Dimensions

| Dimension | Why it matters |
| --- | --- |
| Quality | Must pass task-specific evals, not generic benchmark claims. |
| Safety | Must pass [[safety]] and permission tests for the route. |
| Modality | Text/image/audio/PDF/tool support must match input surfaces. |
| Context/output | Long context is useful only if latency/cost and citation quality pass. |
| Tools | Function calling, file search, web search, computer use, and MCP support affect architecture. |
| Latency/cost | Must fit [[runtime-reliability]] and [[cost-observability]]. |
| Lifecycle | Preview, alias, snapshot, deprecated, and sunsetting states affect release risk. |
| Region/privacy | Provider, cloud surface, endpoint routing, and retention mode affect [[data-privacy-retention]]. |

HELM motivates holistic evaluation across scenarios and metrics rather than single-number benchmark selection. AI Engineering provides the application-level framing: model choice is one component in a system of prompts, data, evaluation, routing, and operations.

## Refresh Workflow

1. Fetch official model docs or model-list API where available.
2. Update registry fields and `checked_at`.
3. Diff model id, capability, pricing config, context, tool, and lifecycle changes.
4. Mark affected [[model-optimization-routing]] entries stale.
5. Rerun route evals before changing production model.
6. Record decision in [[rollout-decision-log]].

## A/B 비교: official registry vs third-party leaderboard

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Third-party leaderboard | 후보 발굴이 빠르고 benchmark 비교가 쉽다. | 가격, context, API feature, lifecycle, retention 조건이 틀릴 수 있다. | 후보 탐색만. |
| B. Official registry | 모델 ID, pricing, context, tool support, lifecycle을 배포 계약에 연결한다. | 수동 refresh와 source diff가 필요하다. | production route 기본값. |

## A/B 비교: direct API price vs tiered/cache/self-hosted cost

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Direct API price | 단순하고 spend 추정이 쉽다. | Google tiered pricing, DeepSeek cache hit/miss, Llama partner/self-hosted 비용을 한 숫자로 섞기 쉽다. | 같은 provider/product 안의 비교. |
| B. Traffic-mix cost model | cache miss/cache hit, prompt length tier, batch/flex, self-host infra를 분리한다. | data collection이 필요하다. | JooPark route budget 기본값. |

## Product Hook

JooPark should expose a model registry page:

- provider and model id;
- active/preview/deprecated/sunsetting state;
- modality and tool support;
- context and max output;
- pricing config id;
- latest eval score per route;
- last checked date and source link;
- routes currently using the model.

The UI should warn when a production route uses a model whose official source has not been checked recently.

## Open Questions

- Which providers should JooPark support first-party versus through a gateway?
- Should preview models be allowed in canary only?
- What stale threshold should apply to model docs: 7 days, 14 days, or 30 days?

## Backlinks

- [[index]]
- [[model-optimization-routing]]
- [[cost-observability]]
- [[runtime-reliability]]
- [[safety]]
- [[data-privacy-retention]]
- [[rollout-decision-log]]
- [[source-governance]]

## References

### Web

- OpenAI. "Model comparison." https://developers.openai.com/api/docs/models/compare
- OpenAI. "API platform." https://openai.com/api/
- Anthropic. "Models overview." https://platform.claude.com/docs/en/about-claude/models/overview
- Google AI for Developers. "Gemini models." https://ai.google.dev/gemini-api/docs/models
- Google AI for Developers. "Gemini Developer API pricing." https://ai.google.dev/gemini-api/docs/pricing
- Meta. "The Llama 4 herd." https://ai.meta.com/blog/llama-4-multimodal-intelligence/
- DeepSeek. "Models and pricing." https://api-docs.deepseek.com/quick_start/pricing
- Mistral AI. "Models overview." https://docs.mistral.ai/models/overview

### Paper

- Liang et al. "Holistic Evaluation of Language Models." arXiv:2211.09110. https://arxiv.org/abs/2211.09110

### Book

- Huyen. "AI Engineering: Building Applications with Foundation Models." O'Reilly, 2025. https://openlibrary.org/books/OL54058212M/AI_Engineering
