---
updated: 2026-06-08T15:38:15+09:00
confidence: high
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_datasets
    type: web
    title: OpenAI Getting started with datasets
    url: https://developers.openai.com/api/docs/guides/evaluation-getting-started
    checked: 2026-06-08
  - id: openai_evals_api
    type: web
    title: OpenAI Evals API reference
    url: https://developers.openai.com/api/reference/resources/evals
    checked: 2026-06-08
  - id: anthropic_eval_tool
    type: web
    title: Anthropic Evaluation Tool documentation
    url: https://anthropic.mintlify.app/en/docs/test-and-evaluate/eval-tool
    checked: 2026-06-08
  - id: huggingface_dataset_cards
    type: web
    title: Hugging Face Dataset Cards
    url: https://huggingface.co/docs/hub/en/datasets-cards
    checked: 2026-06-08
  - id: datasheets_for_datasets
    type: paper
    title: "Datasheets for Datasets"
    authors: Timnit Gebru; Jamie Morgenstern; Briana Vecchione; Jennifer Wortman Vaughan; Hanna Wallach; Hal Daume III; Kate Crawford
    year: 2018
    arxiv: "1803.09010"
    doi: "10.48550/arXiv.1803.09010"
    url: https://arxiv.org/abs/1803.09010
  - id: data_cards
    type: paper
    title: "Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI"
    authors: Pushkarna et al.
    year: 2022
    arxiv: "2204.01075"
    doi: "10.48550/arXiv.2204.01075"
    url: https://arxiv.org/abs/2204.01075
  - id: search_time_contamination
    type: paper
    title: "Search-Time Data Contamination"
    year: 2025
    arxiv: "2508.13180"
    doi: "10.48550/arXiv.2508.13180"
    url: https://arxiv.org/abs/2508.13180
  - id: data_management_for_researchers
    type: book
    title: "Data Management for Researchers"
    authors: Kristin Briney
    year: 2015
    isbn: "9781784270117"
    url: https://openlibrary.org/books/OL28793161M
tags:
  - llm-wiki
  - evals
  - datasets
  - governance
  - contamination
---

# Eval Dataset Governance

[[evaluation]]은 모델 출력 채점만이 아니라 데이터셋 자체의 계약을 관리하는 일이다. JooPark의 `eval_dataset_governance` 노트는 `dataset_id`, `dataset_version`, `dataset_hash`, `schema_version`, `item_schema`, `data_source_config`, `testing_criteria`, `retention_class`, `delete_request_id`, `data_freshness_days`를 최소 필드로 본다.

## Dataset Contract

- OpenAI Datasets는 prompt와 grader를 빠르게 시험하는 dashboard 흐름을 제공하며, CSV 업로드와 visual editing으로 데이터를 추가할 수 있다. 같은 문서의 현재 일정 기준으로 Evals platform은 2026-10-31에 기존 사용자에게 read-only가 되고 2026-11-30에 종료 예정이므로, 이 날짜는 재확인 대상으로 둔다.
- OpenAI Evals API는 eval의 `data_source_config`가 run data schema를 정하고, custom data source schema가 testing criteria와 run 생성에 필요한 데이터 shape를 정의한다.
- Anthropic Evaluation Tool은 수동 row 추가, `Generate Test Case`, CSV import를 제공한다. 자동 생성 테스트는 편하지만, generation logic과 실제 production blind spot을 분리해 기록하지 않으면 synthetic overfitting이 생길 수 있다.
- Hugging Face Dataset Cards는 dataset repo의 `README.md`가 렌더링되는 문서화 표면이며, license, language, size, task metadata, paper link 같은 discovery/governance metadata를 YAML로 둘 수 있다.

## Governance Checklist

| Field | Purpose | JooPark Rule |
| --- | --- | --- |
| `dataset_id` | 안정적인 데이터셋 식별자 | note, eval run, result lineage에서 같은 ID 사용 |
| `dataset_version` | 데이터셋 변경 추적 | row 추가, 삭제, redaction 때 증가 |
| `dataset_hash` | 재현 가능한 snapshot 검증 | JSONL/CSV export의 hash를 저장 |
| `item_schema` | grader가 참조하는 row shape | prompt 변수와 grader 변수를 명시 |
| `data_source_config` | dashboard/API data source 구분 | OpenAI dashboard dataset, JSONL, logs source를 분리 |
| `testing_criteria` | pass/fail 또는 score 기준 | grader version과 threshold를 함께 기록 |
| `retention_class` | 보관/삭제 정책 | PII, secrets, paid API data, synthetic fixture 분리 |
| `delete_request_id` | 삭제 이행 추적 | 민감 row 삭제 요청과 처리 증거를 연결 |

## Contamination Guards

- 공개 benchmark와 private holdout을 섞지 않는다. [[rag-evals]]의 BEIR/MTEB 같은 공개 benchmark는 모델 비교 기준점이고, JooPark의 실제 작업 품질을 닫는 acceptance gate는 별도 private holdout이어야 한다.
- train/test leakage는 exact duplicate만 보지 말고 near_duplicate, n-gram overlap, prompt paraphrase, temporal leakage를 함께 본다.
- search-capable agent eval은 retrieval 단계가 문제/정답 쌍을 찾는 search-time contamination을 만들 수 있다. 검색 로그에 Hugging Face dataset page, GitHub fixture, benchmark answer key가 등장하면 `#검증필요`로 격리한다.
- synthetic_sample은 회귀 테스트 seed로 유용하지만, production_sample 및 consented_sample과 같은 대표성을 주장하면 안 된다.

## Documentation Standard

- Datasheets for Datasets는 motivation, composition, collection process, recommended uses 같은 질문 세트를 통해 dataset producer와 consumer 사이의 투명성을 높이는 방향이다.
- Data Cards는 dataset lifecycle 전체에서 upstream source, collection, annotation, intended use, evaluation method, model performance 영향을 구조화해 stakeholder가 읽을 수 있는 문서로 취급한다.
- JooPark 노트는 Dataset Card/Datasheet를 그대로 복제하지 않고, eval 운영에 필요한 필드만 축약한다. 전문 템플릿이나 책 본문을 붙여 넣지 않는다.

## Backlinks

- [[index]]
- [[rag-evals]]
- [[evaluation]]
- [[eval-result-lineage]]
- [[data-privacy-retention]]
- [[source-governance]]
- [[postmortem-action-ledger]]

## References

### Web

- OpenAI, Getting started with datasets, checked 2026-06-08: https://developers.openai.com/api/docs/guides/evaluation-getting-started
- OpenAI, Evals API reference, checked 2026-06-08: https://developers.openai.com/api/reference/resources/evals
- Anthropic, Evaluation Tool documentation, checked 2026-06-08: https://anthropic.mintlify.app/en/docs/test-and-evaluate/eval-tool
- Hugging Face, Dataset Cards, checked 2026-06-08: https://huggingface.co/docs/hub/en/datasets-cards

### Paper

- Gebru, T.; Morgenstern, J.; Vecchione, B.; Vaughan, J. W.; Wallach, H.; Daume III, H.; Crawford, K. (2018). "Datasheets for Datasets." arXiv:1803.09010. DOI: 10.48550/arXiv.1803.09010. https://arxiv.org/abs/1803.09010
- Pushkarna et al. (2022). "Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI." arXiv:2204.01075. DOI: 10.48550/arXiv.2204.01075. https://arxiv.org/abs/2204.01075
- "Search-Time Data Contamination" (2025). arXiv:2508.13180. DOI: 10.48550/arXiv.2508.13180. https://arxiv.org/abs/2508.13180

### Book

- Briney, K. (2015). "Data Management for Researchers." Pelagic Publishing. ISBN 9781784270117. Open Library: https://openlibrary.org/books/OL28793161M
