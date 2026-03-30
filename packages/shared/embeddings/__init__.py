"""
shared.embeddings — 통합 임베딩 모듈.

기본 임베딩 (Gemini Embedding 2):
    from shared.embeddings import embed_texts, cosine_similarity, deduplicate_texts

AgentIR (Reasoning-Aware Retrieval):
    from shared.embeddings import agentir
    from shared.embeddings.agentir import (
        ReasoningQuery, RetrievalMode, embed_with_reasoning, search
    )
"""

from . import agentir
from .core import (
    compute_similarity_matrix,
    cosine_similarity,
    deduplicate_texts,
    embed_texts,
    embed_texts_async,
)

__all__ = [
    # Core (Gemini Embedding 2)
    "embed_texts",
    "embed_texts_async",
    "cosine_similarity",
    "compute_similarity_matrix",
    "deduplicate_texts",
    # AgentIR module
    "agentir",
]
