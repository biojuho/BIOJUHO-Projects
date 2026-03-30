"""
shared.embeddings.agentir — AgentIR: Reasoning-Aware Retrieval Backend.

에이전트의 reasoning trace를 쿼리와 함께 임베딩하여
Deep Research 검색 정확도를 획기적으로 향상시키는 모듈.

Architecture:
  - Primary: HuggingFace Serverless Inference API (BAAI/bge-small-en-v1.5)
    ※ AgentIR-4B(4B params)는 HF Serverless에 미호스팅.
       GPU 환경 또는 HF Dedicated Endpoints 사용 시 전환 가능.
  - Fallback: Gemini Embedding 2 (기존 shared.embeddings)
  - Caching: TTL 메모리 캐시 (동일 reasoning+query 반복 방지)

Key Insight (from AgentIR paper):
  기존 검색은 쿼리만 사용하지만, 에이전트의 reasoning trace를
  쿼리와 함께 임베딩하면 검색 정확도가 대폭 향상됨.
  - Task Intent: 모호한 쿼리의 의도를 명확화
  - Prior Results: 이전 검색 결과 반영으로 범위 축소
  - Hypotheses: 가설 기반 검색 대상 추론

References:
  - Paper: https://arxiv.org/abs/2603.04384
  - Model: https://huggingface.co/Tevatron/AgentIR-4B
  - GitHub: https://github.com/texttron/AgentIR
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field
from enum import Enum

try:
    from loguru import logger as log
except ImportError:
    import logging as _logging

    log = _logging.getLogger("shared.embeddings.agentir")
    if not log.handlers:
        log.addHandler(_logging.StreamHandler())
        log.setLevel(_logging.DEBUG)


# ══════════════════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════════════════

AGENTIR_MODEL = "Tevatron/AgentIR-4B"  # Reference (requires GPU or HF Endpoints)
HF_EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # HF Serverless 무료 호스팅 모델 (dim=384)
AGENTIR_PREFIX = (
    "Instruct: Given a user's reasoning followed by a web search query, "
    "retrieve relevant passages that answer the query while incorporating "
    "the user's reasoning\nQuery:"
)

# Cache configuration
_CACHE: dict[str, tuple[float, list[float]]] = {}
_CACHE_TTL = 3600  # 1시간
_CACHE_MAX_SIZE = 300


class RetrievalMode(Enum):
    """Agent retrieval modes for different use cases."""

    REASONING_AWARE = "reasoning_aware"  # reasoning trace + query (AgentIR 방식)
    STANDARD = "standard"  # query only (기존 방식)
    HYBRID = "hybrid"  # AgentIR + Gemini 앙상블


@dataclass
class ReasoningQuery:
    """Structured query with reasoning context for AgentIR."""

    query: str
    reasoning: str = ""
    task_context: str = ""
    prior_results: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)

    def to_agentir_input(self) -> str:
        """AgentIR 모델 입력 형식으로 변환."""
        parts = []
        if self.reasoning:
            parts.append(f"Reasoning: {self.reasoning}")
        if self.task_context:
            parts.append(f"Context: {self.task_context}")
        if self.prior_results:
            parts.append(f"Prior findings: {'; '.join(self.prior_results)}")
        if self.hypotheses:
            parts.append(f"Hypotheses: {'; '.join(self.hypotheses)}")
        parts.append(f"Query: {self.query}")
        return " ".join(parts)

    def to_standard_query(self) -> str:
        """기존 방식: 쿼리만 반환."""
        return self.query


@dataclass
class RetrievalResult:
    """검색 결과 with 메타데이터."""

    text: str
    score: float
    index: int
    mode: RetrievalMode = RetrievalMode.STANDARD
    model: str = ""
    latency_ms: float = 0.0


@dataclass
class AgentIRStats:
    """AgentIR 사용 통계."""

    total_calls: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    fallback_calls: int = 0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0

    def record(self, latency_ms: float, cache_hit: bool, fallback: bool = False):
        self.total_calls += 1
        if cache_hit:
            self.cache_hits += 1
        elif fallback:
            self.fallback_calls += 1
        else:
            self.api_calls += 1
        # Running average
        self.avg_latency_ms = (self.avg_latency_ms * (self.total_calls - 1) + latency_ms) / self.total_calls

    def summary(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": f"{self.cache_hits / max(1, self.total_calls) * 100:.1f}%",
            "api_calls": self.api_calls,
            "fallback_calls": self.fallback_calls,
            "avg_latency_ms": f"{self.avg_latency_ms:.1f}",
        }


# ══════════════════════════════════════════════════════
#  Global State
# ══════════════════════════════════════════════════════

_stats = AgentIRStats()


def _cache_key(text: str) -> str:
    """캐시 키 생성."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _evict_expired():
    """만료된 캐시 엔트리 제거."""
    now = time.time()
    expired = [k for k, (ts, _) in _CACHE.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _CACHE[k]


# ══════════════════════════════════════════════════════
#  Core Embedding API
# ══════════════════════════════════════════════════════


def embed_with_reasoning(
    queries: list[ReasoningQuery],
    mode: RetrievalMode = RetrievalMode.REASONING_AWARE,
) -> list[list[float]] | None:
    """
    Reasoning-aware 임베딩: 에이전트의 추론 trace와 쿼리를 함께 벡터화.

    Args:
        queries: ReasoningQuery 객체 목록
        mode: REASONING_AWARE (AgentIR), STANDARD (기존), HYBRID (앙상블)

    Returns:
        벡터 리스트 또는 실패 시 None
    """
    if not queries:
        return None

    start_time = time.time()
    _evict_expired()

    # 쿼리 텍스트 준비
    if mode == RetrievalMode.REASONING_AWARE:
        texts = [f"{AGENTIR_PREFIX} {q.to_agentir_input()}" for q in queries]
    else:
        texts = [q.to_standard_query() for q in queries]

    # 캐시 확인
    results: list[list[float] | None] = [None] * len(texts)
    miss_indices: list[int] = []
    now = time.time()

    for i, text in enumerate(texts):
        key = _cache_key(text)
        cached = _CACHE.get(key)
        if cached and (now - cached[0] < _CACHE_TTL):
            results[i] = cached[1]
        else:
            miss_indices.append(i)

    cache_hits = len(texts) - len(miss_indices)
    if cache_hits:
        log.debug(f"[AgentIR 캐시] {cache_hits}/{len(texts)} 히트")

    if not miss_indices:
        latency = (time.time() - start_time) * 1000
        _stats.record(latency, cache_hit=True)
        return results  # type: ignore

    # HF Inference API 호출
    miss_texts = [texts[i] for i in miss_indices]
    vectors = _embed_via_hf_api(miss_texts)

    if vectors is None:
        # Fallback: Gemini Embedding 2
        log.warning("[AgentIR] HF API 실패 → Gemini Embedding 2 폴백")
        vectors = _embed_via_gemini_fallback([queries[i].to_standard_query() for i in miss_indices])
        if vectors is None:
            _stats.record((time.time() - start_time) * 1000, cache_hit=False, fallback=True)
            return None
        _stats.record((time.time() - start_time) * 1000, cache_hit=False, fallback=True)
    else:
        _stats.record((time.time() - start_time) * 1000, cache_hit=False)

    # 캐시 저장 + 결과 매핑
    for idx, vec in zip(miss_indices, vectors, strict=False):
        key = _cache_key(texts[idx])
        _CACHE[key] = (now, vec)
        results[idx] = vec

    # 캐시 크기 제한
    if len(_CACHE) > _CACHE_MAX_SIZE:
        sorted_keys = sorted(_CACHE, key=lambda k: _CACHE[k][0])
        for k in sorted_keys[: len(_CACHE) - _CACHE_MAX_SIZE]:
            del _CACHE[k]

    log.debug(f"[AgentIR] {len(miss_texts)}개 임베딩 완료 " f"(mode={mode.value}, cache_hits={cache_hits})")
    return results  # type: ignore


async def embed_with_reasoning_async(
    queries: list[ReasoningQuery],
    mode: RetrievalMode = RetrievalMode.REASONING_AWARE,
) -> list[list[float]] | None:
    """비동기 reasoning-aware 임베딩."""
    return await asyncio.to_thread(embed_with_reasoning, queries, mode)


def embed_documents(
    documents: list[str],
) -> list[list[float]] | None:
    """
    문서 임베딩 (패시지/코퍼스용). Reasoning prefix 없이 임베딩.

    Args:
        documents: 임베딩할 문서 텍스트 목록

    Returns:
        벡터 리스트 또는 실패 시 None
    """
    if not documents:
        return None

    _evict_expired()
    now = time.time()

    results: list[list[float] | None] = [None] * len(documents)
    miss_indices: list[int] = []

    for i, doc in enumerate(documents):
        key = _cache_key(f"doc:{doc}")
        cached = _CACHE.get(key)
        if cached and (now - cached[0] < _CACHE_TTL):
            results[i] = cached[1]
        else:
            miss_indices.append(i)

    if not miss_indices:
        return results  # type: ignore

    miss_docs = [documents[i] for i in miss_indices]
    vectors = _embed_via_hf_api(miss_docs)

    if vectors is None:
        vectors = _embed_via_gemini_fallback(miss_docs)
        if vectors is None:
            return None

    for idx, vec in zip(miss_indices, vectors, strict=False):
        key = _cache_key(f"doc:{documents[idx]}")
        _CACHE[key] = (now, vec)
        results[idx] = vec

    return results  # type: ignore


async def embed_documents_async(
    documents: list[str],
) -> list[list[float]] | None:
    """비동기 문서 임베딩."""
    return await asyncio.to_thread(embed_documents, documents)


# ══════════════════════════════════════════════════════
#  Backend Implementations
# ══════════════════════════════════════════════════════


def _normalize_vector(vec: list[float]) -> list[float]:
    """L2 정규화. [QA 수정] 헬퍼 분리."""
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


def _parse_hf_response(result: list) -> list[list[float]]:
    """HF API 응답을 list[list[float]]로 파싱 + 정규화. [QA 수정] 헬퍼 분리."""
    vectors = []
    for item in result:
        if isinstance(item, list) and len(item) > 0:
            if isinstance(item[0], float):
                vec = item  # 이미 1D 벡터
            elif isinstance(item[0], list):
                # 2D: [seq_len, dim] → 평균 풀링
                dim = len(item[0])
                vec = [sum(tok[d] for tok in item) / len(item) for d in range(dim)]
            else:
                vec = item
        else:
            vec = item
        vectors.append(_normalize_vector(vec))
    return vectors


def _embed_via_hf_api(texts: list[str]) -> list[list[float]] | None:
    """
    HuggingFace Serverless Inference API를 통한 임베딩.

    현재: BAAI/bge-small-en-v1.5 (HF 무료 서버리스 호스팅, dim=384)
    향후: Tevatron/AgentIR-4B (GPU 환경 또는 HF Dedicated Endpoints)
    """
    token = os.getenv("HF_TOKEN", os.getenv("HUGGING_FACE_HUB_TOKEN", ""))
    if not token:
        log.debug("[AgentIR] HF_TOKEN 미설정 → HF API 스킵")
        return None

    import urllib.request

    url = f"https://router.huggingface.co/hf-inference/models/{HF_EMBED_MODEL}/pipeline/feature-extraction"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        payload = json.dumps({"inputs": texts}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        if not isinstance(result, list):
            log.warning(f"[AgentIR] HF API 예상치 못한 응답 형식: {type(result)}")
            return None

        vectors = _parse_hf_response(result)

        log.debug(
            f"[AgentIR] HF API 임베딩 성공: {len(texts)}개 → "
            f"model={HF_EMBED_MODEL}, dim={len(vectors[0]) if vectors else 0}"
        )
        return vectors

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        log.warning(f"[AgentIR] HF API HTTP {e.code}: {body}")
        return None
    except Exception as e:
        log.warning(f"[AgentIR] HF API 호출 실패: {e}")
        return None


def _embed_via_gemini_fallback(texts: list[str]) -> list[list[float]] | None:
    """Gemini Embedding 2를 폴백으로 사용."""
    try:
        from shared.embeddings.core import embed_texts

        return embed_texts(texts, task_type="RETRIEVAL_QUERY")
    except Exception as e:
        log.warning(f"[AgentIR] Gemini 폴백도 실패: {e}")
        return None


# ══════════════════════════════════════════════════════
#  Retrieval (Search) API
# ══════════════════════════════════════════════════════


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """코사인 유사도 (0.0 ~ 1.0)."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(
    query: ReasoningQuery,
    documents: list[str],
    doc_vectors: list[list[float]] | None = None,
    top_k: int = 5,
    mode: RetrievalMode = RetrievalMode.REASONING_AWARE,
    threshold: float = 0.0,
) -> list[RetrievalResult]:
    """
    Reasoning-aware 시맨틱 검색.

    Args:
        query: ReasoningQuery 객체
        documents: 검색 대상 문서 목록
        doc_vectors: 사전 계산된 문서 벡터 (없으면 자동 계산)
        top_k: 상위 K개 반환
        mode: 검색 모드
        threshold: 최소 유사도 임계값

    Returns:
        점수 내림차순으로 정렬된 RetrievalResult 목록
    """
    start_time = time.time()

    # 쿼리 벡터 생성
    query_vecs = embed_with_reasoning([query], mode=mode)
    if query_vecs is None or query_vecs[0] is None:
        log.warning("[AgentIR] 쿼리 임베딩 실패")
        return []

    q_vec = query_vecs[0]

    # 문서 벡터 생성 (없으면)
    if doc_vectors is None:
        doc_vectors = embed_documents(documents)
        if doc_vectors is None:
            log.warning("[AgentIR] 문서 임베딩 실패")
            return []

    # 유사도 계산 + 정렬
    scored: list[tuple[int, float]] = []
    for i, d_vec in enumerate(doc_vectors):
        if d_vec is not None:
            sim = cosine_similarity(q_vec, d_vec)
            if sim >= threshold:
                scored.append((i, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:top_k]

    latency = (time.time() - start_time) * 1000

    results = [
        RetrievalResult(
            text=documents[idx],
            score=score,
            index=idx,
            mode=mode,
            model=AGENTIR_MODEL,
            latency_ms=latency,
        )
        for idx, score in scored
    ]

    log.debug(
        f"[AgentIR 검색] top-{top_k} 완료 " f"(mode={mode.value}, latency={latency:.0f}ms, results={len(results)})"
    )
    return results


async def search_async(
    query: ReasoningQuery,
    documents: list[str],
    doc_vectors: list[list[float]] | None = None,
    top_k: int = 5,
    mode: RetrievalMode = RetrievalMode.REASONING_AWARE,
    threshold: float = 0.0,
) -> list[RetrievalResult]:
    """비동기 reasoning-aware 검색."""
    return await asyncio.to_thread(search, query, documents, doc_vectors, top_k, mode, threshold)


# ══════════════════════════════════════════════════════
#  Index Management (Phase 3)
# ══════════════════════════════════════════════════════


@dataclass
class VectorIndex:
    """인메모리 벡터 인덱스 with 영속성 지원."""

    name: str
    documents: list[str] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)
    metadata: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add(
        self,
        documents: list[str],
        vectors: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int:
        """문서 + 벡터 추가. 추가된 수 반환."""
        if len(documents) != len(vectors):
            raise ValueError("documents와 vectors 수 불일치")

        self.documents.extend(documents)
        self.vectors.extend(vectors)
        if metadata:
            self.metadata.extend(metadata)
        else:
            self.metadata.extend([{}] * len(documents))
        self.updated_at = time.time()
        return len(documents)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        filter_fn=None,
    ) -> list[RetrievalResult]:
        """인덱스 내 검색."""
        scored = []
        for i, vec in enumerate(self.vectors):
            if filter_fn and not filter_fn(self.metadata[i]):
                continue
            sim = cosine_similarity(query_vector, vec)
            if sim >= threshold:
                scored.append((i, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            RetrievalResult(
                text=self.documents[idx],
                score=score,
                index=idx,
                model=AGENTIR_MODEL,
            )
            for idx, score in scored[:top_k]
        ]

    def save(self, path: str) -> None:
        """인덱스를 JSON 파일로 저장."""
        data = {
            "name": self.name,
            "documents": self.documents,
            "vectors": self.vectors,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        log.info(f"[AgentIR] 인덱스 '{self.name}' 저장: {path} ({len(self.documents)}개 문서)")

    @classmethod
    def load(cls, path: str) -> VectorIndex:
        """JSON 파일에서 인덱스 로드."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        idx = cls(
            name=data["name"],
            documents=data.get("documents", []),
            vectors=data.get("vectors", []),
            metadata=data.get("metadata", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
        log.info(f"[AgentIR] 인덱스 '{idx.name}' 로드: {path} ({len(idx.documents)}개 문서)")
        return idx

    def __len__(self) -> int:
        return len(self.documents)


# ══════════════════════════════════════════════════════
#  A/B Testing (Phase 3)
# ══════════════════════════════════════════════════════


@dataclass
class ABTestResult:
    """A/B 테스트 개별 결과."""

    query: str
    reasoning_aware_scores: list[float]
    standard_scores: list[float]
    reasoning_aware_top1: str
    standard_top1: str
    improvement: float  # reasoning_aware - standard top-1 score delta


def ab_test_search(
    queries: list[ReasoningQuery],
    documents: list[str],
    doc_vectors: list[list[float]] | None = None,
    top_k: int = 5,
) -> dict:
    """
    Reasoning-Aware vs Standard 검색 A/B 테스트.

    Returns:
        A/B 테스트 통계 + 개별 쿼리별 결과
    """
    if doc_vectors is None:
        doc_vectors = embed_documents(documents)
        if doc_vectors is None:
            return {"error": "문서 임베딩 실패"}

    results: list[ABTestResult] = []
    ra_wins = 0
    std_wins = 0
    ties = 0

    for q in queries:
        # Reasoning-Aware mode
        ra_results = search(q, documents, doc_vectors, top_k, RetrievalMode.REASONING_AWARE)
        # Standard mode
        std_results = search(q, documents, doc_vectors, top_k, RetrievalMode.STANDARD)

        ra_top1_score = ra_results[0].score if ra_results else 0.0
        std_top1_score = std_results[0].score if std_results else 0.0

        improvement = ra_top1_score - std_top1_score

        result = ABTestResult(
            query=q.query,
            reasoning_aware_scores=[r.score for r in ra_results],
            standard_scores=[r.score for r in std_results],
            reasoning_aware_top1=ra_results[0].text[:100] if ra_results else "",
            standard_top1=std_results[0].text[:100] if std_results else "",
            improvement=improvement,
        )
        results.append(result)

        if improvement > 0.01:
            ra_wins += 1
        elif improvement < -0.01:
            std_wins += 1
        else:
            ties += 1

    avg_improvement = sum(r.improvement for r in results) / max(1, len(results))

    summary = {
        "total_queries": len(queries),
        "reasoning_aware_wins": ra_wins,
        "standard_wins": std_wins,
        "ties": ties,
        "avg_score_improvement": f"{avg_improvement:.4f}",
        "win_rate": f"{ra_wins / max(1, len(queries)) * 100:.1f}%",
        "results": [
            {
                "query": r.query,
                "improvement": f"{r.improvement:.4f}",
                "ra_top1_score": f"{r.reasoning_aware_scores[0]:.4f}" if r.reasoning_aware_scores else "N/A",
                "std_top1_score": f"{r.standard_scores[0]:.4f}" if r.standard_scores else "N/A",
            }
            for r in results
        ],
    }

    log.info(
        f"[AgentIR A/B] 완료: RA wins={ra_wins}, STD wins={std_wins}, "
        f"ties={ties}, avg_improvement={avg_improvement:.4f}"
    )
    return summary


# ══════════════════════════════════════════════════════
#  Monitoring & Diagnostics
# ══════════════════════════════════════════════════════


def get_stats() -> dict:
    """AgentIR 사용 통계 반환."""
    return _stats.summary()


def reset_stats() -> None:
    """통계 초기화."""
    global _stats
    _stats = AgentIRStats()


def health_check() -> dict:
    """AgentIR 시스템 헬스 체크."""
    status = {
        "hf_token_set": bool(os.getenv("HF_TOKEN", os.getenv("HUGGING_FACE_HUB_TOKEN", ""))),
        "hf_embed_model": HF_EMBED_MODEL,
        "agentir_reference_model": AGENTIR_MODEL,
        "cache_size": len(_CACHE),
        "cache_max": _CACHE_MAX_SIZE,
        "stats": _stats.summary(),
    }

    # HF API 연결 테스트
    try:
        test_vec = _embed_via_hf_api(["health check test"])
        status["hf_api_healthy"] = test_vec is not None
        if test_vec:
            status["embedding_dim"] = len(test_vec[0])
    except Exception as e:
        status["hf_api_healthy"] = False
        status["hf_api_error"] = str(e)

    # Gemini fallback 테스트
    try:
        from shared.embeddings.core import embed_texts

        test_vec = embed_texts(["health check"], task_type="RETRIEVAL_QUERY")
        status["gemini_fallback_healthy"] = test_vec is not None
    except Exception:
        status["gemini_fallback_healthy"] = False

    return status
