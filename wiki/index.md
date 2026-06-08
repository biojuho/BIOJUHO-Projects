---
updated: 2026-06-08T16:03:32+09:00
confidence: medium
source_types:
  - project
sources:
  - README.md
  - llm-wiki-view.js
tags:
  - llm-wiki
  - autoresearch
  - moc
---

# JooPark LLM Wiki MOC

이 인덱스는 JooPark Workspace의 내장 `LLM 위키`를 Obsidian 노트로 분리해 추적하는 Map of Content입니다. 각 노트는 공식 문서, 논문, 책 메타데이터를 분리해 기록하고, 앱의 검증 스크립트와 이어질 수 있는 키워드를 보존합니다.

## Completed

- [[rag-evals]] - RAG 검색 품질, 임베딩, 파일 검색, citation ledger, recall@k/nDCG@10 평가.
- [[eval-dataset-governance]] - 평가 데이터셋 계약, 데이터 카드, contamination guard, holdout 운영.
- [[eval-result-lineage]] - 평가 결과를 dataset, prompt, model, grader, trace, artifact, release decision에 연결.
- [[evaluator-calibration]] - LLM-as-judge를 human label, rubric, agreement, bias/drift 지표로 보정.
- [[eval-failure-triage]] - eval failure를 root cause, severity, owner, incident workflow로 연결.
- [[rollout-decision-log]] - eval, trace, canary, feature flag, rollback evidence를 release decision으로 연결.
- [[postmortem-action-ledger]] - incident follow-up을 owner, closure gate, eval evidence, recurrence tracking으로 관리.
- [[data-privacy-retention]] - provider retention, ZDR, PII/secret redaction, app TTL, deletion path를 LLM route별로 기록.
- [[agent-tool-permissions]] - agent tool을 tier, scope, approval, audit log, rollback, excessive-agency eval로 통제.
- [[safety]] - prompt injection, system prompt leakage, moderation, sensitive disclosure, excessive agency를 release blocker eval로 관리.
- [[runtime-reliability]] - rate limit, retry, timeout, streaming, overload, fallback, side-effect idempotency를 route SLO로 관리.
- [[deployment-secrets-env]] - API key, env file, secret scanning, OIDC, rotation, BYOK, leak response를 배포 환경별로 관리.
- [[prompt-release-management]] - prompt version, label, model/tool schema, eval gate, cache, rollback을 release artifact로 관리.
- [[model-optimization-routing]] - prompt/RAG/model size/router/batch/distillation 선택을 quality, cost, latency, safety eval로 결정.
- [[multimodal-file-inputs]] - image/PDF/document/audio 입력을 parser, citation, ACL, retention, eval fixture로 관리.
- [[api-examples]] - structured output, tool, MCP server, eval fixture를 route/schema/release id에 연결한 최소 예시로 관리.
- [[cost-observability]] - token, cache, retry, batch, fallback, latency, success metric을 cost per success로 관측.
- [[model-landscape]] - provider/model registry를 official source, modality, context, tool support, lifecycle, route fit으로 갱신.
- [[source-governance]] - source hierarchy, freshness SLA, provenance, stale-claim workflow, `#검증필요` 운영 규칙을 관리.

## Queue

Queue exhausted on 2026-06-08 after Cycle 019.

## Operating Rules

- 최신 API 표면이나 가격, 모델명은 30일 이상 지나면 stale 후보로 본다.
- 공식 문서와 표준을 먼저 붙이고, 논문은 평가 방법과 benchmark 한계를 설명하는 데 쓴다.
- 책은 개념/정의 수준만 사용하며 본문 전문을 복제하지 않는다.
- 불확실하거나 출처가 충돌하는 항목은 `#검증필요`로 남긴다.
