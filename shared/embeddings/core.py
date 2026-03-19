"""
shared.embeddings.core — Gemini Embedding 2 Preview 벡터 임베딩 + 유사도 + 중복 제거.

Features:
  - 동기/비동기 텍스트 임베딩
  - 코사인 유사도 + N×N 매트릭스
  - 의미적 중복 제거 (deduplicate_texts)
  - LRU 캐시로 동일 텍스트 반복 호출 방지
  - API 실패 시 graceful None 반환 (호출자가 폴백 결정)

Free Tier: 분당 5~15요청, 일 ~1,000요청
유료: $0.10 / 100만 토큰 (텍스트)
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
from functools import lru_cache
from typing import Optional

try:
    from loguru import logger as log
except ImportError:
    import logging as _logging

    log = _logging.getLogger("shared.embeddings")
    if not log.handlers:
        log.addHandler(_logging.StreamHandler())
        log.setLevel(_logging.DEBUG)


# ══════════════════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════════════════

EMBEDDING_MODEL = "gemini-embedding-2-preview"
DEFAULT_DIMENSIONS = 768  # 768 → 클러스터링/중복제거에 충분, 메모리/속도 절약

# [v14.1] TTL 메모리 캐시 (동일 텍스트 반복 임베딩 방지)
_EMBED_CACHE: dict[str, tuple[float, list[float]]] = {}
_CACHE_TTL = 7200  # 2시간 (초)
_CACHE_MAX_SIZE = 500  # 최대 캐시 항목 수


def _cache_key(text: str, dimensions: int, task_type: str) -> str:
    """캐시 키 생성."""
    raw = f"{text}|{dimensions}|{task_type}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _evict_expired() -> None:
    """만료된 캐시 항목 제거."""
    import time
    now = time.time()
    expired = [k for k, (ts, _) in _EMBED_CACHE.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _EMBED_CACHE[k]


# ══════════════════════════════════════════════════════
#  Client Singleton
# ══════════════════════════════════════════════════════

_client = None


def _get_genai_client():
    """google-genai Client 싱글턴 (lazy init)."""
    global _client
    if _client is not None:
        return _client

    try:
        from google import genai
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            log.warning("[임베딩] GOOGLE_API_KEY 미설정 → 임베딩 비활성화")
            return None
        _client = genai.Client(api_key=api_key)
        return _client
    except ImportError:
        log.warning("[임베딩] google-genai 패키지 미설치 → pip install google-genai")
        return None
    except Exception as e:
        log.error(f"[임베딩] GenAI 클라이언트 초기화 실패: {e}")
        return None


# ══════════════════════════════════════════════════════
#  Embedding API
# ══════════════════════════════════════════════════════

def embed_texts(
    texts: list[str],
    dimensions: int = DEFAULT_DIMENSIONS,
    task_type: str = "CLUSTERING",
) -> Optional[list[list[float]]]:
    """
    텍스트 목록을 Gemini Embedding 2로 벡터화 (동기).

    Args:
        texts: 임베딩할 텍스트 목록
        dimensions: 출력 벡터 차원 (768, 1536, 3072)
        task_type: CLUSTERING, RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY 등

    Returns:
        벡터 리스트 또는 실패 시 None
    """
    if not texts:
        return None

    client = _get_genai_client()
    if client is None:
        return None

    import time as _time
    _evict_expired()

    # 캐시 히트/미스 분리
    now = _time.time()
    results: list[list[float] | None] = [None] * len(texts)
    miss_indices: list[int] = []

    for i, text in enumerate(texts):
        key = _cache_key(text, dimensions, task_type)
        cached = _EMBED_CACHE.get(key)
        if cached and (now - cached[0] < _CACHE_TTL):
            results[i] = cached[1]
        else:
            miss_indices.append(i)

    cache_hits = len(texts) - len(miss_indices)
    if cache_hits:
        log.debug(f"[임베딩 캐시] {cache_hits}/{len(texts)} 히트")

    if not miss_indices:
        return results  # type: ignore[return-value]

    # 미스된 텍스트만 API 호출
    miss_texts = [texts[i] for i in miss_indices]

    try:
        from google.genai import types

        config = types.EmbedContentConfig(
            output_dimensionality=dimensions,
            task_type=task_type,
        )

        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=miss_texts,
            config=config,
        )

        vectors = [emb.values for emb in result.embeddings]

        # 결과를 캐시에 저장하고 results에 배치
        for idx, vec in zip(miss_indices, vectors):
            key = _cache_key(texts[idx], dimensions, task_type)
            _EMBED_CACHE[key] = (now, vec)
            results[idx] = vec

        # 캐시 크기 제한
        if len(_EMBED_CACHE) > _CACHE_MAX_SIZE:
            sorted_keys = sorted(_EMBED_CACHE, key=lambda k: _EMBED_CACHE[k][0])
            for k in sorted_keys[:len(_EMBED_CACHE) - _CACHE_MAX_SIZE]:
                del _EMBED_CACHE[k]

        log.debug(f"[임베딩] {len(miss_texts)}개 API 호출 + {cache_hits}개 캐시 → 총 {len(texts)}개 완료")
        return results  # type: ignore[return-value]

    except Exception as e:
        log.warning(f"[임베딩] API 호출 실패: {e}")
        return None


async def embed_texts_async(
    texts: list[str],
    dimensions: int = DEFAULT_DIMENSIONS,
    task_type: str = "CLUSTERING",
) -> Optional[list[list[float]]]:
    """비동기 임베딩 — asyncio.to_thread로 래핑."""
    return await asyncio.to_thread(embed_texts, texts, dimensions, task_type)


# ══════════════════════════════════════════════════════
#  코사인 유사도
# ══════════════════════════════════════════════════════

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터 간 코사인 유사도 (0.0 ~ 1.0)."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_similarity_matrix(vectors: list[list[float]]) -> list[list[float]]:
    """벡터 목록 → N×N 유사도 매트릭스."""
    n = len(vectors)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            sim = cosine_similarity(vectors[i], vectors[j])
            matrix[i][j] = sim
            matrix[j][i] = sim
    return matrix


# ══════════════════════════════════════════════════════
#  의미적 중복 제거
# ══════════════════════════════════════════════════════

def deduplicate_texts(
    texts: list[str],
    threshold: float = 0.80,
    key_fn=None,
) -> list[int]:
    """
    의미적으로 중복되는 텍스트를 제거하고 고유 인덱스 반환.

    Args:
        texts: 비교할 텍스트 목록
        threshold: 이 값 이상이면 중복으로 판정 (기본 0.80)
        key_fn: 텍스트 전처리 함수 (None이면 원문 그대로)

    Returns:
        고유 텍스트의 인덱스 목록 (중복 제거 후)

    Example::

        titles = ["삼성전자 주가 급등", "삼성전자 주가 크게 상승", "비트코인 신고가"]
        unique_indices = deduplicate_texts(titles, threshold=0.80)
        # → [0, 2]  ("삼성전자 주가 급등"과 "크게 상승"은 중복으로 1개만 유지)
    """
    if len(texts) <= 1:
        return list(range(len(texts)))

    processed = [key_fn(t) if key_fn else t for t in texts]
    vectors = embed_texts(processed, task_type="SEMANTIC_SIMILARITY")

    if vectors is None:
        log.debug("[중복 제거] 임베딩 실패 → 전체 유지")
        return list(range(len(texts)))

    # 그리디 중복 제거: 앞에서부터 순회, 이미 선택된 것과 유사하면 스킵
    selected: list[int] = []
    for i in range(len(texts)):
        is_dup = False
        for j in selected:
            sim = cosine_similarity(vectors[i], vectors[j])
            if sim >= threshold:
                log.debug(
                    f"[중복 제거] '{texts[i][:30]}' ↔ '{texts[j][:30]}' "
                    f"= {sim:.3f} ≥ {threshold} → 제거"
                )
                is_dup = True
                break
        if not is_dup:
            selected.append(i)

    removed = len(texts) - len(selected)
    if removed:
        log.info(f"[중복 제거] {len(texts)}개 → {len(selected)}개 ({removed}개 의미적 중복 제거)")

    return selected
