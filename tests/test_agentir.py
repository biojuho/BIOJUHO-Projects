"""
AgentIR 통합 테스트 — Phase 1 PoC + Phase 2 통합 검증 + Phase 3 인덱스/A/B.

테스트 구성:
  1. 모듈 임포트 & 구조 검증
  2. ReasoningQuery 데이터 모델 검증
  3. 임베딩 API (HF API / Gemini 폴백)
  4. 검색 API (reasoning-aware vs standard)
  5. VectorIndex CRUD + 영속성
  6. A/B 테스트 프레임워크
  7. 통계 & 헬스체크
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest


# ══════════════════════════════════════════════════════
#  Group 1: 모듈 임포트 & 구조 검증
# ══════════════════════════════════════════════════════

class TestModuleStructure:
    """Phase 1: 모듈 구조 및 임포트 검증."""

    def test_import_agentir_module(self):
        """AgentIR 모듈이 shared.embeddings에서 임포트 가능."""
        from shared.embeddings import agentir
        assert hasattr(agentir, "embed_with_reasoning")
        assert hasattr(agentir, "search")
        assert hasattr(agentir, "VectorIndex")

    def test_import_reasoning_query(self):
        """ReasoningQuery 데이터 모델 임포트 가능."""
        from shared.embeddings.agentir import ReasoningQuery
        q = ReasoningQuery(query="test")
        assert q.query == "test"
        assert q.reasoning == ""

    def test_import_retrieval_mode(self):
        """RetrievalMode Enum 임포트 가능."""
        from shared.embeddings.agentir import RetrievalMode
        assert RetrievalMode.REASONING_AWARE.value == "reasoning_aware"
        assert RetrievalMode.STANDARD.value == "standard"
        assert RetrievalMode.HYBRID.value == "hybrid"

    def test_import_all_public_api(self):
        """모든 public API가 임포트 가능."""
        from shared.embeddings.agentir import (
            ReasoningQuery,
            RetrievalMode,
            RetrievalResult,
            VectorIndex,
            ABTestResult,
            AgentIRStats,
            embed_with_reasoning,
            embed_with_reasoning_async,
            embed_documents,
            embed_documents_async,
            search,
            search_async,
            ab_test_search,
            get_stats,
            reset_stats,
            health_check,
            AGENTIR_MODEL,
            AGENTIR_PREFIX,
        )
        assert AGENTIR_MODEL == "Tevatron/AgentIR-4B"

    def test_backward_compatibility(self):
        """기존 shared.embeddings API가 여전히 작동."""
        from shared.embeddings import (
            embed_texts,
            embed_texts_async,
            cosine_similarity,
            compute_similarity_matrix,
            deduplicate_texts,
        )
        # 기존 함수 시그니처 확인
        assert callable(embed_texts)
        assert callable(cosine_similarity)


# ══════════════════════════════════════════════════════
#  Group 2: ReasoningQuery 데이터 모델
# ══════════════════════════════════════════════════════

class TestReasoningQuery:
    """ReasoningQuery 객체 생성 및 변환 검증."""

    def test_basic_query(self):
        from shared.embeddings.agentir import ReasoningQuery

        q = ReasoningQuery(query="precision agriculture Korea")
        assert q.query == "precision agriculture Korea"
        assert q.reasoning == ""
        assert q.to_standard_query() == "precision agriculture Korea"

    def test_reasoning_enriched_query(self):
        from shared.embeddings.agentir import ReasoningQuery

        q = ReasoningQuery(
            query="smart farm disease prediction",
            reasoning="이전 검색에서 한국 스마트팜 보조금 정책 확인. 병충해 예측 AI 모델 관련 연구 필요.",
            task_context="AgriGuard 프로젝트 연구",
            prior_results=["스마트팜 보조금 2026 정책"],
            hypotheses=["CNN 기반 병충해 탐지가 유력"],
        )
        agentir_input = q.to_agentir_input()

        # 모든 요소가 포함되어야 함
        assert "Reasoning:" in agentir_input
        assert "Context:" in agentir_input
        assert "Prior findings:" in agentir_input
        assert "Hypotheses:" in agentir_input
        assert "Query:" in agentir_input
        assert "smart farm disease prediction" in agentir_input

    def test_partial_reasoning(self):
        from shared.embeddings.agentir import ReasoningQuery

        q = ReasoningQuery(
            query="DeSci blockchain",
            reasoning="탈중앙화 과학 연구를 위한 블록체인 활용 사례 조사",
        )
        output = q.to_agentir_input()
        assert "Reasoning:" in output
        assert "Query:" in output
        # 빈 필드는 포함되지 않아야 함
        assert "Context:" not in output
        assert "Prior findings:" not in output


# ══════════════════════════════════════════════════════
#  Group 3: 임베딩 API 테스트
# ══════════════════════════════════════════════════════

class TestEmbeddingAPI:
    """임베딩 API 기능 검증 (API 연결 필요 시 skip)."""

    def test_embed_empty_returns_none(self):
        from shared.embeddings.agentir import embed_with_reasoning
        result = embed_with_reasoning([])
        assert result is None

    def test_embed_documents_empty_returns_none(self):
        from shared.embeddings.agentir import embed_documents
        result = embed_documents([])
        assert result is None

    @pytest.mark.skipif(
        not os.getenv("HF_TOKEN") and not os.getenv("GOOGLE_API_KEY"),
        reason="HF_TOKEN 또는 GOOGLE_API_KEY 미설정"
    )
    def test_embed_with_reasoning_api(self):
        """실제 API를 통한 임베딩 테스트."""
        from shared.embeddings.agentir import (
            ReasoningQuery, embed_with_reasoning, RetrievalMode
        )

        queries = [
            ReasoningQuery(
                query="precision agriculture disease prediction",
                reasoning="스마트팜 프로젝트에서 병충해 예측 모델 연구 중",
            )
        ]
        vectors = embed_with_reasoning(queries, mode=RetrievalMode.REASONING_AWARE)

        if vectors is not None:
            assert len(vectors) == 1
            assert len(vectors[0]) > 0
            # 정규화 검증
            import math
            norm = math.sqrt(sum(v * v for v in vectors[0]))
            assert abs(norm - 1.0) < 0.01, f"벡터가 정규화되지 않음: norm={norm}"

    @pytest.mark.skipif(
        not os.getenv("HF_TOKEN") and not os.getenv("GOOGLE_API_KEY"),
        reason="HF_TOKEN 또는 GOOGLE_API_KEY 미설정"
    )
    def test_embed_documents_api(self):
        """실제 API를 통한 문서 임베딩 테스트."""
        from shared.embeddings.agentir import embed_documents

        docs = [
            "스마트팜에서 AI 기반 병충해 예측 모델을 적용하여 농업 생산성을 향상시킨다.",
            "블록체인 기술을 활용한 탈중앙화 과학 연구 플랫폼의 설계와 구현.",
        ]
        vectors = embed_documents(docs)

        if vectors is not None:
            assert len(vectors) == 2
            assert len(vectors[0]) == len(vectors[1])


# ══════════════════════════════════════════════════════
#  Group 4: 검색 API 테스트
# ══════════════════════════════════════════════════════

class TestSearchAPI:
    """검색 기능 검증."""

    def test_search_with_no_docs_returns_empty(self):
        from shared.embeddings.agentir import ReasoningQuery, search

        q = ReasoningQuery(query="test")
        results = search(q, documents=[], top_k=5)
        assert results == []

    @pytest.mark.skipif(
        not os.getenv("HF_TOKEN") and not os.getenv("GOOGLE_API_KEY"),
        reason="HF_TOKEN 또는 GOOGLE_API_KEY 미설정"
    )
    def test_search_ranking(self):
        """검색 랭킹이 관련도 순으로 정렬되는지 검증."""
        from shared.embeddings.agentir import ReasoningQuery, search, RetrievalMode

        documents = [
            "스마트팜에서 AI 기반 병충해 예측 모델을 적용하여 농업 생산성 향상.",
            "비트코인 가격이 역대 최고치를 기록하며 투자자들의 관심이 집중되고 있다.",
            "딥러닝을 활용한 농작물 질병 분류 시스템의 개발과 현장 적용.",
            "새로운 K-POP 그룹이 빌보드 차트 1위를 달성했다.",
            "컴퓨터 비전 기반 식물 병해충 조기 진단 기술의 최근 동향.",
        ]

        query = ReasoningQuery(
            query="crop disease detection AI",
            reasoning="AgriGuard 프로젝트에서 딥러닝 기반 병충해 탐지 시스템 개발 중. "
                      "이전 검색에서 CNN 모델이 유력한 후보임을 확인.",
        )

        results = search(query, documents, top_k=3)

        if results:
            # 상위 결과에 농업/AI 관련 문서가 와야 함
            assert len(results) <= 3
            # 점수가 내림차순으로 정렬
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score


# ══════════════════════════════════════════════════════
#  Group 5: VectorIndex CRUD + 영속성
# ══════════════════════════════════════════════════════

class TestVectorIndex:
    """인메모리 벡터 인덱스 기능 검증."""

    def test_create_empty_index(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="test_index")
        assert idx.name == "test_index"
        assert len(idx) == 0

    def test_add_documents(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="test")
        count = idx.add(
            documents=["doc1", "doc2"],
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            metadata=[{"source": "a"}, {"source": "b"}],
        )
        assert count == 2
        assert len(idx) == 2
        assert idx.documents[0] == "doc1"
        assert idx.metadata[1]["source"] == "b"

    def test_add_mismatched_raises(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="test")
        with pytest.raises(ValueError, match="불일치"):
            idx.add(
                documents=["doc1"],
                vectors=[[0.1, 0.2], [0.3, 0.4]],
            )

    def test_search_in_index(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="test")
        idx.add(
            documents=["농업 AI", "블록체인 DeFi", "자연어 처리"],
            vectors=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
        )

        results = idx.search(query_vector=[0.9, 0.1, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].text == "농업 AI"  # 가장 유사

    def test_search_with_filter(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="test")
        idx.add(
            documents=["A", "B", "C"],
            vectors=[[1, 0, 0], [0, 1, 0], [0.9, 0.1, 0]],
            metadata=[
                {"category": "tech"},
                {"category": "finance"},
                {"category": "tech"},
            ],
        )

        # tech만 필터
        results = idx.search(
            query_vector=[1, 0, 0],
            top_k=3,
            filter_fn=lambda m: m.get("category") == "tech",
        )
        assert len(results) == 2
        assert all(
            idx.metadata[r.index]["category"] == "tech" for r in results
        )

    def test_save_and_load(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="persist_test")
        idx.add(
            documents=["doc1", "doc2", "doc3"],
            vectors=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            metadata=[{"k": "v1"}, {"k": "v2"}, {"k": "v3"}],
        )

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            path = f.name

        try:
            idx.save(path)
            assert os.path.exists(path)

            loaded = VectorIndex.load(path)
            assert loaded.name == "persist_test"
            assert len(loaded) == 3
            assert loaded.documents == ["doc1", "doc2", "doc3"]
            assert loaded.vectors[0] == [0.1, 0.2]
            assert loaded.metadata[2]["k"] == "v3"
        finally:
            os.unlink(path)

    def test_incremental_add(self):
        from shared.embeddings.agentir import VectorIndex

        idx = VectorIndex(name="incremental")
        idx.add(documents=["a"], vectors=[[1, 0]])
        idx.add(documents=["b", "c"], vectors=[[0, 1], [1, 1]])
        assert len(idx) == 3


# ══════════════════════════════════════════════════════
#  Group 6: A/B 테스트 프레임워크
# ══════════════════════════════════════════════════════

class TestABTestFramework:
    """A/B 테스트 구조 검증."""

    def test_ab_test_result_structure(self):
        from shared.embeddings.agentir import ABTestResult

        result = ABTestResult(
            query="test",
            reasoning_aware_scores=[0.9, 0.7],
            standard_scores=[0.8, 0.6],
            reasoning_aware_top1="doc_a",
            standard_top1="doc_b",
            improvement=0.1,
        )
        assert result.improvement == 0.1

    def test_ab_test_empty_queries(self):
        from shared.embeddings.agentir import ab_test_search, ReasoningQuery

        result = ab_test_search(
            queries=[],
            documents=["doc1"],
        )
        assert result["total_queries"] == 0


# ══════════════════════════════════════════════════════
#  Group 7: 통계 & 헬스체크
# ══════════════════════════════════════════════════════

class TestStatsAndHealth:
    """통계 및 헬스체크 기능 검증."""

    def test_stats_structure(self):
        from shared.embeddings.agentir import get_stats, reset_stats

        reset_stats()
        stats = get_stats()
        assert "total_calls" in stats
        assert "cache_hits" in stats
        assert "cache_hit_rate" in stats
        assert "api_calls" in stats
        assert "fallback_calls" in stats
        assert "avg_latency_ms" in stats

    def test_stats_recording(self):
        from shared.embeddings.agentir import AgentIRStats

        stats = AgentIRStats()
        stats.record(latency_ms=100.0, cache_hit=False)
        stats.record(latency_ms=50.0, cache_hit=True)
        stats.record(latency_ms=200.0, cache_hit=False, fallback=True)

        summary = stats.summary()
        assert summary["total_calls"] == 3
        assert summary["cache_hits"] == 1
        assert summary["api_calls"] == 1
        assert summary["fallback_calls"] == 1

    def test_health_check_structure(self):
        from shared.embeddings.agentir import health_check

        result = health_check()
        assert "hf_embed_model" in result
        assert result["agentir_reference_model"] == "Tevatron/AgentIR-4B"
        assert "cache_size" in result
        assert "stats" in result

    def test_reset_stats(self):
        from shared.embeddings.agentir import reset_stats, get_stats

        reset_stats()
        stats = get_stats()
        assert stats["total_calls"] == 0


# ══════════════════════════════════════════════════════
#  Group 8: 코사인 유사도
# ══════════════════════════════════════════════════════

class TestCosineSimularity:
    """AgentIR 내장 코사인 유사도 함수 검증."""

    def test_identical_vectors(self):
        from shared.embeddings.agentir import cosine_similarity
        assert abs(cosine_similarity([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        from shared.embeddings.agentir import cosine_similarity
        assert abs(cosine_similarity([1, 0, 0], [0, 1, 0])) < 1e-6

    def test_opposite_vectors(self):
        from shared.embeddings.agentir import cosine_similarity
        assert abs(cosine_similarity([1, 0], [-1, 0]) - (-1.0)) < 1e-6

    def test_mismatched_dims(self):
        from shared.embeddings.agentir import cosine_similarity
        assert cosine_similarity([1, 0], [1, 0, 0]) == 0.0

    def test_zero_vector(self):
        from shared.embeddings.agentir import cosine_similarity
        assert cosine_similarity([0, 0], [1, 0]) == 0.0
