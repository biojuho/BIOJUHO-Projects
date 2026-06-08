---
updated: 2026-06-08T15:57:11+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_prompt_engineering
    type: web
    title: OpenAI prompt engineering guide
    url: https://developers.openai.com/api/docs/guides/prompt-engineering
    checked: 2026-06-08
  - id: openai_prompt_guidance
    type: web
    title: OpenAI prompt guidance
    url: https://developers.openai.com/api/docs/guides/prompt-guidance
    checked: 2026-06-08
  - id: openai_prompt_caching
    type: web
    title: OpenAI prompt caching
    url: https://developers.openai.com/api/docs/guides/prompt-caching
    checked: 2026-06-08
  - id: openai_eval_best_practices
    type: web
    title: OpenAI evaluation best practices
    url: https://developers.openai.com/api/docs/guides/evaluation-best-practices
    checked: 2026-06-08
  - id: openai_production_best_practices
    type: web
    title: OpenAI production best practices
    url: https://developers.openai.com/api/docs/guides/production-best-practices
    checked: 2026-06-08
  - id: openai_model_snapshots
    type: web
    title: OpenAI model snapshots
    url: https://developers.openai.com/api/docs/models/gpt-5.5
    checked: 2026-06-08
  - id: anthropic_prompt_engineering_overview
    type: web
    title: Anthropic prompt engineering overview
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
    checked: 2026-06-08
  - id: anthropic_prompting_tools
    type: web
    title: Anthropic prompting tools
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-tools
    checked: 2026-06-08
  - id: anthropic_prompt_caching
    type: web
    title: Anthropic prompt caching
    url: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
    checked: 2026-06-08
  - id: langfuse_prompt_management
    type: web
    title: Langfuse prompt management overview
    url: https://langfuse.com/docs/prompt-management/overview
    checked: 2026-06-08
  - id: langfuse_prompt_version_control
    type: web
    title: Langfuse prompt version control
    url: https://langfuse.com/docs/prompt-management/features/prompt-version-control
    checked: 2026-06-08
  - id: prompt_report
    type: paper
    title: "The Prompt Report: A Systematic Survey of Prompting Techniques"
    url: https://arxiv.org/abs/2406.06608
    checked: 2026-06-08
  - id: prompt_engineering_book
    type: book
    title: "Prompt Engineering for Generative AI"
    url: https://openlibrary.org/books/OL50951839M/Prompt_Engineering_for_Generative_AI
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - prompts
  - release
  - versioning
  - prompt-cache
---

# Prompt Release Management

Prompt release management treats prompts as versioned production artifacts. A release unit includes prompt text, model settings, tool schemas, retrieval contract, safety controls, eval results, cache behavior, and rollback target.

## Prompt Release Contract

```js
const promptRelease = {
  prompt_id: "support_triage_system",
  prompt_version: 17,
  registry_label: "staging|production|rollback|experiment",
  model_route: "gpt-5.5",
  parameters: { temperature: 0.2, max_output_tokens: 900 },
  tool_schema_version: "workspace_search@3+ticket_draft@2",
  retrieval_contract_id: "support-rag-v4",
  safety_policy_version: "safety-route-support-v3",
  cache_sensitive_prefix_hash: "sha256:...",
  eval_run_ids: ["evalrun_..."],
  release_decision_id: "rdl-20260608-006",
  previous_production_version: 16,
  approver: "prompt_owner",
  change_summary: "tighten citation-before-answer and refusal boundary",
  created_at: "2026-06-08T15:55:34+09:00",
};
```

## Prompt Config Bundle

Every production prompt release should be stored as a `prompt_config_bundle`, not just as prompt text:

```js
const prompt_config_bundle = {
  prompt_id: "support-triage",
  prompt_version: "2026-06-08.3",
  prompt_hash: "sha256:...",
  registry_label: "production",
  model_alias: "gpt-5.5",
  model_snapshot: "gpt-5.5-2026-04-23",
  developer_message_version: "devmsg-v7",
  schema_version: "triage-json/v4",
  tool_schema_version: "crm-tools/v2",
  retrieval_version: "kb-embeddings-2026-06",
  safety_policy_version: "safe-comms/v5",
  eval_suite_version: "triage-evals/v12",
  rollout_stage: "canary-10pct",
  rollback_target: "2026-06-07.2",
};
```

OpenAI prompt engineering separates `developer and user messages`; release management should version the developer message and inject user content, retrieved context, and tool outputs through typed variables. OpenAI prompt guidance is model-specific, so `model-specific prompt tuning` should not be mixed with registry-label movement without a new eval receipt. OpenAI prompt caching makes a `stable prompt prefix` and `cached_tokens` operationally visible. Anthropic prompting tools define `prompt templates and variables`, prompt generator, prompt improver, and evaluation tool workflows. Langfuse describes prompt management as storing, versioning, retrieving prompts with `version ID`, `labels`, `production`, `staging`, `prod-a`, and `prod-b`; `protected prompt labels` should guard the production label.

## Release Rules

- Never promote a prompt only because manual testing looks better.
- Attach eval run ids from [[rag-evals]], [[safety]], and task-specific score suites.
- Version model parameters, tool schemas, retrieval contract, and safety policy with the prompt.
- Keep `latest` and `production` concepts separate.
- Protect production labels so only approved roles can move them.
- Keep rollback target explicit and tested.
- Track prompt cache-sensitive prefix changes because cache behavior affects latency and cost.
- Do not store secrets or private policy in prompts; link to [[deployment-secrets-env]] and [[data-privacy-retention]].

Langfuse documents prompt management with versions and labels, including production labels. OpenAI prompt caching makes stable shared prefixes operationally relevant because cache hit rate affects latency and cost. OpenAI eval guidance supplies the release gate for prompt changes and supports `eval-driven development`.

## Source A/B Findings

| Comparison | A | B | JooPark decision |
| --- | --- | --- | --- |
| Prompt structure | OpenAI emphasizes developer/user message separation and prompt guidance that can vary by model family. | Anthropic tooling emphasizes templates, variables, generator, improver, and evaluation workflows. | Store both message roles and template variables inside the release bundle. |
| Release registry | Code-only prompt changes use normal review and deployment discipline. | Langfuse-style registry labels allow staging/production/prod-a/prod-b promotion and rollback by label revert. | Security-critical prompts can stay in code; high-iteration product prompts use protected registry labels. |
| Cache and rollout | OpenAI prompt caching rewards a stable prompt prefix and exposes cached_tokens. | Canary release metrics catch user-facing quality, refusal, and cost regressions. | Require cache warmup and canary-10pct evidence before production label movement. |

## Lifecycle

1. Draft: create a new version with change summary and owner.
2. Static review: check prompt variables, tool schemas, forbidden secrets, and policy text.
3. Offline eval: run regression, safety, and route-specific evals.
4. Shadow/canary: attach the prompt release to [[rollout-decision-log]].
5. Promote: move production label only after gates pass.
6. Monitor: compare failure clusters, cost, latency, and user feedback.
7. Rollback: restore previous production version and record reason.

## A/B Comparison

| Choice | Strength | Weakness | Adoption |
| --- | --- | --- | --- |
| Prompt in code | Strong code review and deployment discipline. | Slow iteration and hard for domain experts. | Good for security-critical system prompts. |
| Prompt registry | Fast versioning, labels, experiments, and runtime fetch. | Needs RBAC and release gates. | Good for product prompts and route variants. |
| Ad hoc prompt edits | Fastest. | No lineage, rollback, or eval evidence. | Disallowed for production. |

## A/B 비교: hardcoded prompts in code vs prompt registry labels

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Hardcoded prompts in code | 코드 리뷰, test, deploy 흐름이 명확하고 감사가 쉽다. | 작은 prompt 수정도 code deploy가 필요하고 도메인 전문가 반복이 느리다. | 규제·보안 민감 경로, 초기 제품. |
| B. Prompt registry labels | `production`/`staging` label로 빠른 실험과 rollback 가능. | registry RBAC, label drift, cache/trace 연결을 별도 관리해야 한다. | 빈번한 prompt 실험과 다팀 운영. |

## A/B 비교: model alias vs pinned model snapshot

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Model alias | 최신 개선을 자동 수용하고 운영 부담이 낮다. | 동작 변화 원인 분석과 rollback이 어렵다. | low-risk assistant, 탐색형 기능. |
| B. Pinned model snapshot | prompt_version과 model behavior를 재현 가능하게 묶는다. | 최신 성능 개선을 수동 승격해야 한다. | 중요한 workflow와 eval 기반 릴리스. |

## A/B 비교: big-bang prompt deploy vs staged eval/canary

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Big-bang deploy | 운영이 단순하고 빠르다. | prompt regression이 전체 사용자에게 즉시 노출된다. | 내부 도구·낮은 트래픽. |
| B. Staged eval/canary | golden dataset, regression set, safety probes, shadow, canary-10pct로 회귀를 좁은 범위에서 발견한다. | 실험 설계와 telemetry 비용이 증가한다. | user-facing production 기본값. |

## Prompt Cache Notes

- Stable shared prefixes can improve latency/cost when provider caching applies.
- Cache behavior should not be treated as correctness evidence.
- Prompt variables should appear after stable policy/tool sections when possible.
- Large prompt changes can shift cost, latency, and model behavior at the same time; evaluate all three.
- Product UI should show `cached_tokens`, cache warmup status, and cache hit rate through [[cost-observability]].

## Eval Hooks

| Eval | Checks |
| --- | --- |
| `prompt_regression_suite` | New version beats or matches current production on core tasks. |
| `prompt_safety_suite` | Prompt resists direct/indirect injection and does not leak hidden instructions. |
| `tool_instruction_accuracy` | Tool call conditions and parameters remain correct. |
| `citation_behavior` | Prompt cites only supported sources. |
| `cache_cost_latency` | Prefix changes do not create unacceptable cost/latency regressions. |
| `release_canary` | `user_correction_rate`, `refusal_rate`, and `cost_per_success` do not regress during canary-10pct. |

## Rollback Runbook

The rollback runbook must be executable from the release record:

1. Freeze new prompt label movement.
2. Move the production label back to `rollback_target` with a label revert.
3. Run cache warmup for the restored stable prompt prefix.
4. Rerun golden dataset, regression set, and safety probes.
5. Record the rollback decision in [[rollout-decision-log]] and open [[postmortem-action-ledger]] action items if the regression escaped canary.

## Product Hook

JooPark should expose a prompt release page:

- prompt id, version, label, owner, approver;
- diff from previous production;
- eval trend and blocker clusters;
- linked rollout decision;
- rollback version;
- prompt cache metrics;
- production label audit trail.

## Open Questions

- Which prompts are security-critical enough to stay in code?
- Who can move `production` labels?
- Should prompt releases be bundled with model route changes or separated?

## Backlinks

- [[index]]
- [[rollout-decision-log]]
- [[rag-evals]]
- [[safety]]
- [[eval-result-lineage]]
- [[cost-observability]]
- [[model-optimization-routing]]
- [[deployment-secrets-env]]
- [[source-governance]]

## References

### Web

- OpenAI. "Prompt engineering." https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI. "Prompt guidance." https://developers.openai.com/api/docs/guides/prompt-guidance
- OpenAI. "Prompt caching." https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI. "Evaluation best practices." https://developers.openai.com/api/docs/guides/evaluation-best-practices
- OpenAI. "Production best practices." https://developers.openai.com/api/docs/guides/production-best-practices
- OpenAI. "GPT-5.5 model." https://developers.openai.com/api/docs/models/gpt-5.5
- Anthropic. "Prompt engineering overview." https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
- Anthropic. "Console prompting tools." https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-tools
- Anthropic. "Prompt caching." https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Langfuse. "Prompt Management." https://langfuse.com/docs/prompt-management/overview
- Langfuse. "Prompt Version Control." https://langfuse.com/docs/prompt-management/features/prompt-version-control

### Paper

- Schulhoff et al. "The Prompt Report: A Systematic Survey of Prompting Techniques." arXiv:2406.06608. https://arxiv.org/abs/2406.06608

### Book

- Phoenix and Taylor. "Prompt Engineering for Generative AI." O'Reilly, 2024. ISBN 9781098153434. https://openlibrary.org/books/OL50951839M/Prompt_Engineering_for_Generative_AI
