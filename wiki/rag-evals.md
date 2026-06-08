---
updated: 2026-06-08T15:36:25+09:00
confidence: high
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_text_embedding_3_large
    type: web
    title: OpenAI text-embedding-3-large model docs
    url: https://developers.openai.com/api/docs/models/text-embedding-3-large
    checked: 2026-06-08
  - id: openai_file_search
    type: web
    title: OpenAI File Search guide
    url: https://developers.openai.com/api/docs/guides/tools-file-search
    checked: 2026-06-08
  - id: openai_evals
    type: web
    title: OpenAI Evals API reference
    url: https://developers.openai.com/api/reference/resources/evals
    checked: 2026-06-08
  - id: anthropic_citations
    type: web
    title: Anthropic Claude Citations documentation
    url: https://platform.claude.com/docs/en/build-with-claude/citations
    checked: 2026-06-08
  - id: beir
    type: paper
    title: "BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models"
    authors: Nandan Thakur; Nils Reimers; Andreas Rueckle; Abhishek Srivastava; Iryna Gurevych
    year: 2021
    arxiv: "2104.08663"
    doi: "10.48550/arXiv.2104.08663"
    url: https://arxiv.org/abs/2104.08663
  - id: mteb
    type: paper
    title: "MTEB: Massive Text Embedding Benchmark"
    authors: Niklas Muennighoff; Nouamane Tazi; Loic Magne; Nils Reimers
    year: 2022
    arxiv: "2210.07316"
    doi: "10.48550/arXiv.2210.07316"
    url: https://arxiv.org/abs/2210.07316
  - id: information_retrieval_book
    type: book
    title: "Information Retrieval: Implementing and Evaluating Search Engines"
    authors: Stefan Buettcher; Charles L. A. Clarke; Gordon V. Cormack
    year: 2016
    isbn: "9780262528870"
    url: https://openlibrary.org/books/OL31929645M/Information_Retrieval
tags:
  - llm-wiki
  - rag
  - evals
  - retrieval
  - embeddings
---

# RAG/Evals

RAG 품질은 [[source-governance]]와 [[evaluation]]의 교차점이다. 검색 파이프라인이 문서를 가져오는 것만으로는 충분하지 않고, 어떤 문서가 검색되었는지, 답변이 어떤 근거를 사용했는지, 같은 질문 세트에서 recall@k와 nDCG@10이 어떻게 움직이는지를 함께 남겨야 한다.

## Working Model

- [[embeddings]] 계층은 질의와 문서를 같은 벡터 공간에서 비교하는 검색 후보 생성 단계다. OpenAI `text-embedding-3-large`는 텍스트 입력/출력 임베딩 모델로 문서 검색, 클러스터링, 추천, 분류 같은 관련도 작업에 맞춰 설명된다.
- [[rag]] 계층은 retrieved context를 답변 생성에 연결한다. OpenAI File Search는 `vector_store_ids`로 검색 대상 vector store를 지정하고, 원하면 `include: ["file_search_call.results"]`로 검색 결과를 응답에 포함해 검사할 수 있다.
- 답변 근거는 provider-native citation 기능만 믿지 말고 app-owned citation ledger로도 남긴다. Anthropic Citations는 문서 블록에 `citations.enabled=true`를 켜고 PDF page range, plain text character range, custom content block range 같은 위치 포인터를 반환한다.
- [[evaluation]] 계층은 "답이 좋아 보인다"가 아니라 fixed dataset, expected answer 또는 grading rubric, retrieval metric, generation metric을 따로 둔다. OpenAI Evals는 eval 구조와 run data source schema를 분리해 testing criteria와 run input shape를 정의한다.

## Metrics

| Metric | Use | Failure Signal |
| --- | --- | --- |
| recall@k | 정답 근거 문서가 상위 k 검색 결과 안에 들어오는지 측정 | 답변 모델 이전에 retrieval miss가 발생 |
| nDCG@10 | graded relevance가 있는 검색 결과의 순위 품질 측정 | 관련 문서가 검색되지만 낮은 순위로 밀림 |
| citation coverage | 답변 주장 중 출처 위치가 붙은 비율 | grounded answer처럼 보이지만 추적 불가 |
| answer faithfulness | 검색 근거와 답변 문장의 일치 | retrieved context를 무시하거나 없는 주장을 생성 |

## Product Contract For JooPark

- `llm-wiki-view.js`의 `embeddings`, `rag`, `evaluation` 항목은 `text-embedding-3-large`, `dimensions`, `vector_store_ids`, `include: ["file_search_call.results"]`, `citations.enabled`, `recall@k`, `nDCG@10`, `testing_criteria` marker를 유지한다.
- RAG 관련 UI나 문서가 "검색됨"을 주장할 때는 최소한 `retrieval_query`, `vector_store_id`, `retrieved_document_id`, `rank`, `score`, `citation_span`, `eval_dataset_id`를 ledger 후보로 남긴다.
- BEIR는 domain/task가 다른 검색 benchmark로 out-of-distribution retrieval을 점검하는 기준점이고, MTEB는 embedding 모델을 retrieval뿐 아니라 여러 embedding task에서 비교하는 기준점이다. 둘 다 실제 JooPark 개인 데이터와 동일한 분포라는 뜻은 아니므로 private holdout set 결과와 분리한다.
- 책 메타데이터는 IR 평가가 검색 엔진 구현과 실험의 일부라는 안정된 배경지식으로만 사용한다. 책 본문은 복제하지 않는다.

## Open Questions

- `llm-wiki-view.js` 내부 source registry와 `./wiki` Markdown 노트의 source schema를 장기적으로 한쪽에서 생성할지 아직 결정되지 않았다. #검증필요
- 앱이 자체 RAG를 실행하게 되면 localStorage에 citation ledger를 둘지, exportable JSONL artifact로 둘지 결정해야 한다. #검증필요

## Backlinks

- [[index]]
- [[source-governance]]
- [[embeddings]]
- [[rag]]
- [[evaluation]]
- [[eval-dataset-governance]]
- [[eval-result-lineage]]
- [[runtime-reliability]]
- [[data-privacy-retention]]

## References

### Web

- OpenAI, `text-embedding-3-large` model docs, checked 2026-06-08: https://developers.openai.com/api/docs/models/text-embedding-3-large
- OpenAI, File Search guide, checked 2026-06-08: https://developers.openai.com/api/docs/guides/tools-file-search
- OpenAI, Evals API reference, checked 2026-06-08: https://developers.openai.com/api/reference/resources/evals
- Anthropic, Claude Citations documentation, checked 2026-06-08: https://platform.claude.com/docs/en/build-with-claude/citations

### Paper

- Thakur, N.; Reimers, N.; Rueckle, A.; Srivastava, A.; Gurevych, I. (2021). "BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models." arXiv:2104.08663. DOI: 10.48550/arXiv.2104.08663. https://arxiv.org/abs/2104.08663
- Muennighoff, N.; Tazi, N.; Magne, L.; Reimers, N. (2022). "MTEB: Massive Text Embedding Benchmark." arXiv:2210.07316. DOI: 10.48550/arXiv.2210.07316. https://arxiv.org/abs/2210.07316

### Book

- Buettcher, S.; Clarke, C. L. A.; Cormack, G. V. (2016). "Information Retrieval: Implementing and Evaluating Search Engines." The MIT Press. ISBN 9780262528870. Open Library: https://openlibrary.org/books/OL31929645M/Information_Retrieval

