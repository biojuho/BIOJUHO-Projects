# Migrate to Qdrant Vector Database (POC)

**Labels**: `research`, `performance`, `backend`
**Priority**: 📊 **Medium** - 1개월 내

---

## Description

biolinker의 ChromaDB를 Qdrant로 마이그레이션하여 프로덕션 확장성을 확보합니다.

---

## Current State

- **Vector DB**: ChromaDB (PersistentClient, 로컬 모드)
- **Use case**: RFP 문서 벡터 검색

---

## Qdrant Advantages

- 클라우드 네이티브 (샤드 이동, 리샤딩)
- 멀티 테넌시 지원
- 고급 필터링 (metadata + 벡터 하이브리드)
- gRPC 지원 (낮은 지연시간)

---

## Tasks

- [ ] Qdrant Docker Compose 설정
- [ ] Qdrant Python 클라이언트 설치
- [ ] ChromaDB → Qdrant 마이그레이션 스크립트
- [ ] API 호환 레이어 구현 (`vector_store.py` 리팩토링)
- [ ] 성능 벤치마크 (검색 속도, 인덱싱 속도)
- [ ] 동시성 테스트 (100+ concurrent queries)
- [ ] 비용 분석 (Qdrant Cloud vs self-hosted)
- [ ] 롤백 계획

---

## Benchmark Metrics

- 검색 지연시간 (p50, p95, p99)
- 인덱싱 처리량 (docs/sec)
- 메모리 사용량
- 동시 쿼리 처리 능력

---

## Acceptance Criteria

- ✅ POC 환경에서 기존 기능 100% 동작
- ✅ 검색 지연시간 p95 < 200ms
- ✅ 벤치마크 리포트 작성
- ✅ Go/No-Go 결정 (마이그레이션 여부)

---

**Estimated Time**: 5-7일 (POC)
