"""
shared.embeddings — Gemini Embedding 2 기반 의미적 유사도 공유 모듈.

모든 프로젝트에서 사용:
    from shared.embeddings import embed_texts, cosine_similarity, deduplicate_texts
"""

from .core import (
    cosine_similarity,
    compute_similarity_matrix,
    deduplicate_texts,
    embed_texts,
    embed_texts_async,
)

__all__ = [
    "embed_texts",
    "embed_texts_async",
    "cosine_similarity",
    "compute_similarity_matrix",
    "deduplicate_texts",
]
