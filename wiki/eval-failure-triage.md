---
updated: 2026-06-08T15:44:36+09:00
confidence: high
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: openai_evals
    type: web
    title: OpenAI Evals API
    url: https://developers.openai.com/api/docs/guides/evals
    checked: 2026-06-08
  - id: openai_agents_tracing
    type: web
    title: OpenAI Agents SDK tracing
    url: https://openai.github.io/openai-agents-python/tracing/
    checked: 2026-06-08
  - id: langfuse_scores
    type: web
    title: Langfuse scores overview
    url: https://langfuse.com/docs/evaluation/scores/overview
    checked: 2026-06-08
  - id: langfuse_experiment_data_model
    type: web
    title: Langfuse experiment data model
    url: https://langfuse.com/docs/evaluation/experiments/data-model
    checked: 2026-06-08
  - id: google_sre_incident_management
    type: web
    title: Google SRE incident management
    url: https://sre.google/sre-book/managing-incidents/
    checked: 2026-06-08
  - id: nist_sp_800_61r3
    type: standard
    title: NIST SP 800-61 Rev. 3
    url: https://csrc.nist.gov/pubs/sp/800/61/r3/final
    checked: 2026-06-08
  - id: tool_augmented_llm_failure_taxonomy
    type: paper
    title: "A Taxonomy of Failures in Tool-Augmented LLMs"
    url: https://homes.cs.washington.edu/~rjust/publ/WinstonJ2025-abstract.html
    checked: 2026-06-08
  - id: google_sre_book
    type: book
    title: "Site Reliability Engineering: How Google Runs Production Systems"
    url: https://openlibrary.org/books/OL27208603M
    checked: 2026-06-08
  - id: owasp_llm01
    type: standard
    title: "OWASP LLM01:2025 Prompt Injection"
    url: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
    checked: 2026-06-08
  - id: owasp_llm02
    type: standard
    title: "OWASP LLM02:2025 Sensitive Information Disclosure"
    url: https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/
    checked: 2026-06-08
  - id: owasp_llm06
    type: standard
    title: "OWASP LLM06:2025 Excessive Agency"
    url: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
    checked: 2026-06-08
tags:
  - llm-wiki
  - evals
  - triage
  - incidents
  - safety
---

# Eval Failure Triage

Evaluation failures are not just failing rows. JooPark treats `eval_failure_triage` as the bridge between [[eval-result-lineage]], [[evaluator-calibration]], incident response, and follow-up action ledgers. A failure is only useful when it has a cluster, owner, severity, evidence, and mitigation path.

## Failure Triage Taxonomy

```js
const failureTriageTaxonomy = {
  failure_cluster_id: "fc-support-20260608-014",
  incident_id: "inc-20260608-llm-eval-002",
  severity: "sev2",
  user_impact: "incorrect support triage answer",
  blast_radius: "canary-10pct",
  detection_source: "offline_eval_and_shadow_trace",
  score_name: "groundedness",
  score_value: 0.42,
  score_comment: "cited stale policy page",
  score_data_type: "NUMERIC|CATEGORICAL|BOOLEAN|TEXT",
  failure_mode: "retrieval_miss",
  root_cause_layer: "retrieval",
  symptom: "answer cites unrelated document",
  attribution_confidence: 0.81,
  owner_team: "search-platform",
  time_to_detect_ms: 320000,
  time_to_triage_ms: 540000,
  time_to_mitigate_ms: 1800000,
  cluster_signature_hash: "sha256:...",
  representative_trace_id: "trace_...",
  runbook_id: "rb-rag-retrieval-regression",
  mitigation_status: "investigating",
  postmortem_required: true,
};
```

## Reference Comparison

| Reference | Strength | Limit | JooPark adoption |
| --- | --- | --- | --- |
| OpenAI Evals, graders, Agents tracing | Failing eval row, grader result, report URL, full execution traces를 연결하기 좋음 | incident severity, owner, communication role까지는 앱이 직접 정해야 함 | eval result + trace span을 triage intake로 사용 |
| Langfuse scores and experiment data model | NUMERIC/CATEGORICAL/BOOLEAN/TEXT score, score_comment, DatasetRun, sourceTraceId/sourceObservationId를 보존 | root-cause taxonomy와 postmortem ownership은 별도 운영 계약 필요 | score row를 `failure_cluster_id` 후보로 승격 |
| Google SRE incident management | Incident Commander, Operations, Communication, Planning 역할 분리와 live incident doc이 강함 | LLM-specific prompt/tool/safety failure taxonomy는 제공하지 않음 | severity 있는 eval regression에는 role separation 적용 |
| NIST SP 800-61 Rev. 3 and OWASP LLM risks | incident response를 CSF 2.0 risk management에 연결하고 LLM01/02/06 safety/security impact를 분류 | product quality regression과 model judge drift는 직접 다루지 않음 | security/safety failures는 prompt injection, sensitive disclosure, excessive agency로 태깅 |
| Google SRE book | postmortem, incident role, reliability 운영 개념이 안정적 | API/eval-specific schema는 없음 | severe eval regression의 운영 언어와 action closure 기준으로 사용 |

## Failure Modes

- retrieval: `retrieval_miss`, `retrieval_irrelevant`, `generator_ignored_top_doc`, `citation_mismatch`, `stale_context`.
- prompt/model/grader: `prompt_regression`, `schema_violation`, `judge_drift`, `data_drift`, `label_drift`.
- tool: `tool_selection_error`, `tool_parameter_error`, `tool_execution_error`, `tool_result_interpretation_error`.
- safety/agency: `policy_violation`, `pii_leak`, `excessive_agency`, `guardrail_false_positive`, `guardrail_false_negative`.
- runtime: `latency_regression`, `cost_regression`, `rate_limit_regression`.

## Triage Lifecycle

1. New: cluster_signature_hash appears and a representative_trace_id is selected.
2. Acknowledged: owner_team, severity, and runbook_id are assigned.
3. Investigating: root_cause_layer is narrowed with retrieval span, tool span, grader output, and source trace evidence.
4. Mitigated: prompt rollback, retrieval index rebuild, tool schema fix, policy update, or model routing change is applied.
5. Verified: same dataset_version, calibration set, or shadow_set is replayed and the score returns above threshold.
6. Archived: postmortem_required failures produce a blameless postmortem and a follow-up action in [[postmortem-action-ledger]].

## A/B 비교: manual taxonomy vs embedding clustering

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Manual taxonomy | owner_team, severity, runbook_id가 명확하고 재발 방지 action으로 이어짐 | 새 failure_mode 발견이 느리고 triage 부하가 큼 | release-blocking incident 기본값 |
| B. Embedding clustering | 비슷한 free-form failure를 빠르게 묶고 long-tail pattern discovery가 쉬움 | symptom similarity가 root cause를 보장하지 않음 | annotation queue pre-cluster와 discovery 보조 |

## A/B 비교: symptom cluster vs root-cause cluster

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Symptom cluster | 사용자 영향과 UX wording을 빠르게 파악 | retrieval, tool, prompt 원인이 섞여 mitigation이 흐림 | support/communication summary |
| B. Root-cause cluster | owner_team과 fix path가 선명 | attribution_confidence가 낮을 때 과도한 확신 위험 | engineering triage와 release gate |

## A/B 비교: eval-only triage vs incident workflow

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Eval-only triage | 개발 중 빠르고 lightweight | user_impact, blast_radius, communication owner, postmortem이 빠지기 쉬움 | local prompt/RAG tuning |
| B. Incident workflow | severity, owner, mitigation, communications, postmortem까지 닫힘 | 운영 절차 비용이 듦 | production regression, safety/data/tool failure 기본값 |

## Current Source Caveat

NIST SP 800-61 Rev. 2 is withdrawn and superseded by Rev. 3 as of 2025-04-03. Keep the legacy `NIST SP 800-61` marker for compatibility with the existing verifier, but use Rev. 3 for current incident response guidance.

## Backlinks

- [[index]]
- [[evaluation]]
- [[eval-result-lineage]]
- [[evaluator-calibration]]
- [[postmortem-action-ledger]]
- [[rollout-decision-log]]
- [[data-privacy-retention]]
- [[agent-tool-permissions]]
- [[source-governance]]

## References

### Web

- OpenAI, Evals API, checked 2026-06-08: https://developers.openai.com/api/docs/guides/evals
- OpenAI Agents SDK, tracing, checked 2026-06-08: https://openai.github.io/openai-agents-python/tracing/
- Langfuse, scores overview, checked 2026-06-08: https://langfuse.com/docs/evaluation/scores/overview
- Langfuse, experiments data model, checked 2026-06-08: https://langfuse.com/docs/evaluation/experiments/data-model
- Google SRE, Managing Incidents, checked 2026-06-08: https://sre.google/sre-book/managing-incidents/

### Standard

- NIST, SP 800-61 Rev. 3, checked 2026-06-08: https://csrc.nist.gov/pubs/sp/800/61/r3/final
- OWASP, LLM01:2025 Prompt Injection, checked 2026-06-08: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP, LLM02:2025 Sensitive Information Disclosure, checked 2026-06-08: https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/
- OWASP, LLM06:2025 Excessive Agency, checked 2026-06-08: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/

### Paper

- Winston et al. (2025). "A Taxonomy of Failures in Tool-Augmented LLMs." https://homes.cs.washington.edu/~rjust/publ/WinstonJ2025-abstract.html

### Book

- Beyer, Jones, Petoff, and Murphy. "Site Reliability Engineering: How Google Runs Production Systems." O'Reilly, 2016. ISBN 9781491929124. https://openlibrary.org/books/OL27208603M
