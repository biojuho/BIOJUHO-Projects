---
updated: 2026-06-08T15:40:17+09:00
confidence: high
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: openai_evals_api
    type: web
    title: OpenAI Evals API
    url: https://developers.openai.com/api/docs/guides/evals
    checked: 2026-06-08
  - id: openai_graders
    type: web
    title: OpenAI graders
    url: https://developers.openai.com/api/docs/guides/graders
    checked: 2026-06-08
  - id: openai_agents_tracing
    type: web
    title: OpenAI Agents SDK tracing
    url: https://openai.github.io/openai-agents-python/tracing/
    checked: 2026-06-08
  - id: langfuse_experiments
    type: web
    title: Langfuse experiments via SDK and data model
    url: https://langfuse.com/docs/evaluation/experiments/data-model
    checked: 2026-06-08
  - id: mlflow_tracking
    type: web
    title: MLflow Tracking
    url: https://mlflow.org/docs/latest/ml/tracking/
    checked: 2026-06-08
  - id: opentelemetry_genai
    type: standard
    title: OpenTelemetry GenAI semantic conventions
    url: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
    checked: 2026-06-08
  - id: w3c_prov_dm
    type: standard
    title: W3C PROV-DM
    url: https://www.w3.org/TR/prov-dm/
    checked: 2026-06-08
  - id: ml_lifecycle_artifacts_survey
    type: paper
    title: "Management of Machine Learning Lifecycle Artifacts: A Survey"
    authors: Marius Schlegel; Kai-Uwe Sattler
    year: 2022
    arxiv: "2210.11831"
    doi: "10.48550/arXiv.2210.11831"
    url: https://arxiv.org/abs/2210.11831
  - id: mlflow_paper
    type: paper
    title: "Accelerating the Machine Learning Lifecycle with MLflow"
    authors: Matei Zaharia; Andrew Chen; Aaron Davidson; Ali Ghodsi; Sue Ann Hong; Andy Konwinski; Siddharth Murching; Tomas Nykodym; Paul Ogilvie; Mani Parkhe; Fen Xie; Corey Zumar
    year: 2018
    url: https://people.eecs.berkeley.edu/~matei/papers/2018/ieee_mlflow.pdf
  - id: designing_data_intensive_applications
    type: book
    title: "Designing Data-Intensive Applications"
    authors: Martin Kleppmann
    year: 2017
    isbn: "9781491903117"
    url: https://openlibrary.org/books/OL36735720M/Designing_Data-Intensive_Applications
  - id: openai_data_controls
    type: web
    title: OpenAI platform data controls
    url: https://developers.openai.com/api/docs/guides/your-data
    checked: 2026-06-08
tags:
  - llm-wiki
  - evals
  - lineage
  - tracing
  - provenance
---

# Eval Result Lineage

[[eval-dataset-governance]]가 데이터셋 계약을 고정한다면, `eval_result_lineage`는 어떤 dataset, prompt, model, grader, trace, code, artifact가 특정 release decision을 만들었는지 재현하는 계약이다. JooPark의 기본값은 vendor dashboard URL만 저장하지 않고 app-owned experiment ledger를 남기는 것이다.

## Lineage Contract

```js
const evalResultLineageContract = {
  experiment_id: "support-triage-eval",
  experiment_run_id: "run-20260608-001",
  eval_id: "eval_...",
  eval_run_id: "evalrun_...",
  result_id: "result-...",
  report_url: "https://platform.openai.com/evaluation/evals/...",
  result_counts: { total: 200, passed: 184, failed: 16, errored: 0 },
  dataset_id: "support-triage-v4",
  dataset_version: "2026-06-08.1",
  dataset_hash: "sha256:...",
  dataset_run_id: "dataset-run-...",
  source_trace_id: "trace_...",
  source_observation_id: "obs_...",
  trace_id: "trace_...",
  span_id: "span_...",
  parent_id: "span_parent_...",
  workflow_name: "support-triage",
  group_id: "release-20260608",
  prompt_id: "triage-answer",
  prompt_version: "42",
  prompt_hash: "sha256:...",
  model_alias: "reasoning-prod",
  model_snapshot: "provider-returned-model-id",
  provider_name: "openai",
  grader_id: "groundedness-v3",
  grader_version: "2026-06-08.0",
  grader_type: "score_model",
  pass_threshold: 0.75,
  metric_name: "groundedness",
  metric_value: 0.91,
  artifact_uri: "artifacts/evals/run-20260608-001/results.jsonl",
  raw_results_jsonl: "artifacts/evals/run-20260608-001/raw_results.jsonl",
  confusion_matrix_uri: "artifacts/evals/run-20260608-001/confusion.json",
  code_version: "git:...",
  config_hash: "sha256:...",
  lineage_schema_version: "eval-result-lineage/v1",
  decision_id: "release-gate-20260608",
  rollback_target: "prompt_version:41",
  retention_class: "eval-result-365d",
  redaction_status: "pii_redacted",
  failure_cluster_id: "fc-...",
  lineage_complete: false,
};
```

`lineage_complete=false`는 실패 상태다. release gate는 `eval_run_id`, `report_url`, `result_counts`만으로 닫히지 않고 dataset, prompt, model, grader, trace, code, artifact hash가 모두 채워져야 한다.

## Reference Comparison

| Reference | Strength | Limit | JooPark adoption |
| --- | --- | --- | --- |
| OpenAI Evals + graders | `data_source_config`, `eval_run_id`, `result_counts`, `report_url`, `pass_threshold`, `score_model`을 빠르게 연결 | dashboard/vendor retention에 의존하면 cross-provider replay와 raw artifact 보존이 약함 | OpenAI run output은 fast feedback으로 쓰고 ledger에는 ids, hashes, raw JSONL, grader version을 복사 |
| Langfuse experiments | `DatasetRun`, evaluator score, `sourceTraceId`, `sourceObservationId`로 dataset item과 trace를 연결 | Langfuse object model만으로 release rollback target과 provider-neutral provenance를 전부 표현하지는 않음 | production trace에서 온 case는 source trace keys를 유지하고 JooPark ledger의 release decision id와 합침 |
| MLflow Tracking | run, experiment, params, metrics, artifacts, code version을 범용 실험 저장소로 관리 | LLM-specific trace/span, prompt, grader semantics는 별도 schema가 필요 | quality, cost, latency metric과 JSONL artifacts의 장기 보관 backend 후보 |
| OpenTelemetry + W3C PROV-DM | OpenTelemetry는 runtime span 검색에 강하고 PROV-DM은 Entity/Activity/Agent derivation 설명에 강함 | OpenTelemetry GenAI conventions는 Development status이고 PROV graph는 구현 비용이 큼 | runtime에는 `gen_ai.*` attributes, 감사/장기 재현성에는 minimal PROV graph를 병행 |

## Minimal Join Keys

- identity: `experiment_id`, `experiment_run_id`, `eval_id`, `eval_run_id`, `result_id`, `dataset_run_id`, `decision_id`.
- inputs: `dataset_id`, `dataset_version`, `dataset_hash`, `item_id`, `prompt_id`, `prompt_version`, `prompt_hash`, `model_snapshot`, `config_hash`.
- execution: `trace_id`, `span_id`, `parent_id`, `workflow_name`, `group_id`, `source_trace_id`, `source_observation_id`, provider request id.
- scoring: `grader_id`, `grader_version`, `grader_type`, `score_model`, `pass_threshold`, `metric_name`, `metric_value`, `result_counts`, `failure_cluster_id`.
- artifacts: `report_url`, `artifact_uri`, `raw_results_jsonl`, `confusion_matrix_uri`, `diff_view_url`, `code_version`.
- governance: `lineage_schema_version`, `retention_class`, `redaction_status`, `delete_request_id`, `reviewer_id`, `approval_status`, `rollback_target`.

## Operating Rules

- OpenAI Agents SDK tracing is useful for workflow, span, tool, handoff, and guardrail debugging, but ZDR organizations cannot rely on that hosted trace surface. Long-running workers should call `flush_traces()` only after the trace context closes when immediate export proof is required.
- OpenTelemetry GenAI span attributes are useful for live debugging, but because the GenAI semantic convention is still marked Development, JooPark should version its own `lineage_schema_version` and avoid treating the external attribute set as immutable.
- W3C PROV-DM maps eval artifacts to Entity, eval runner and grader execution to Activity, and reviewer or release approver to Agent. Store `wasGeneratedBy`, `used`, `wasDerivedFrom`, `wasAssociatedWith` only when they answer a real audit question.
- Privacy deletion must follow the same join keys across dataset item, eval result, trace, annotation, raw JSONL, and artifacts. A `delete_request_id` that only touches application rows is incomplete.
- ML lifecycle artifact research frames datasets, features, models, hyperparameters, metrics, software, configurations, and logs as reproducibility/traceability artifacts. JooPark should treat eval reports and prompt bundles as the same class of artifact, not as disposable UI output.
- Book-level data-system guidance is used only as stable background: reliable data applications depend on explicit storage, processing, consistency, and maintainability tradeoffs. The book content is not copied into this note.

## A/B 비교: vendor dashboard result vs app-owned experiment ledger

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Vendor dashboard result | 설정이 빠르고 `report_url`로 사람이 바로 볼 수 있음 | retention, raw export, cross-provider 비교, deprecation risk에 약함 | 빠른 분석과 reviewer 탐색 |
| B. App-owned experiment ledger | 재현성, redaction, retention, release gate 자동화에 강함 | schema, migration, storage 운영 필요 | JooPark production 기본값 |

## A/B 비교: trace-first debugging vs eval-first release gate

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Trace-first debugging | 한 실패의 tool/retrieval/model 경로를 빠르게 추적 | aggregate quality와 regression threshold를 보장하지 않음 | incident triage |
| B. Eval-first release gate | 배포 전 품질, 비용, 안전 기준을 수치로 닫음 | 원인 분석에는 trace join이 필요 | release decision |

## A/B 비교: OpenTelemetry attributes vs W3C PROV graph

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. OpenTelemetry attributes | 기존 observability backend 검색과 alerting에 강함 | derivation과 artifact relation 표현이 약함 | runtime debug |
| B. W3C PROV graph | Entity/Activity/Agent 관계와 derivation 설명이 명확함 | 제품 로그에 그대로 쓰기엔 모델링 비용이 큼 | audit, compliance, 장기 재현성 |

## Open Questions

- JooPark의 실제 LLM 기능이 생기면 ledger 저장 위치를 localStorage, exportable JSONL, 또는 external artifact store 중 어디로 둘지 결정해야 한다. #검증필요
- `model_snapshot`은 provider별 naming stability가 다르므로, alias와 exact returned model id를 함께 보관해야 한다. #검증필요

## Backlinks

- [[index]]
- [[evaluation]]
- [[eval-dataset-governance]]
- [[eval-failure-triage]]
- [[evaluator-calibration]]
- [[postmortem-action-ledger]]
- [[rollout-decision-log]]
- [[data-privacy-retention]]
- [[source-governance]]

## References

### Web

- OpenAI, Evals API, checked 2026-06-08: https://developers.openai.com/api/docs/guides/evals
- OpenAI, graders, checked 2026-06-08: https://developers.openai.com/api/docs/guides/graders
- OpenAI Agents SDK, tracing, checked 2026-06-08: https://openai.github.io/openai-agents-python/tracing/
- OpenAI, platform data controls, checked 2026-06-08: https://developers.openai.com/api/docs/guides/your-data
- Langfuse, experiments data model, checked 2026-06-08: https://langfuse.com/docs/evaluation/experiments/data-model
- Langfuse, experiments via SDK, checked 2026-06-08: https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk
- MLflow, Tracking, checked 2026-06-08: https://mlflow.org/docs/latest/ml/tracking/

### Standard

- OpenTelemetry, GenAI semantic conventions, checked 2026-06-08: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- W3C, PROV-DM, checked 2026-06-08: https://www.w3.org/TR/prov-dm/

### Paper

- Schlegel, M.; Sattler, K.-U. (2022). "Management of Machine Learning Lifecycle Artifacts: A Survey." arXiv:2210.11831. DOI: 10.48550/arXiv.2210.11831. https://arxiv.org/abs/2210.11831
- Zaharia, M.; Chen, A.; Davidson, A.; Ghodsi, A.; Hong, S. A.; Konwinski, A.; Murching, S.; Nykodym, T.; Ogilvie, P.; Parkhe, M.; Xie, F.; Zumar, C. (2018). "Accelerating the Machine Learning Lifecycle with MLflow." https://people.eecs.berkeley.edu/~matei/papers/2018/ieee_mlflow.pdf

### Book

- Kleppmann, M. (2017). "Designing Data-Intensive Applications." O'Reilly Media. ISBN 9781491903117. Open Library: https://openlibrary.org/books/OL36735720M/Designing_Data-Intensive_Applications
