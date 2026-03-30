"""
shared.search.hybrid — Hybrid keyword + semantic search.

Combines BM25-style keyword scoring with vector cosine similarity
for Reciprocal Rank Fusion (RRF) re-ranking.  Works with any
collection of documents that have text + embeddings.

Usage::
    from shared.search.hybrid import hybrid_search

    results = hybrid_search(
        query="AI drug discovery",
        documents=docs,  # list of dicts with 'id', 'text', 'embedding'
        query_embedding=emb,  # query vector
        top_k=5,
    )
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class HybridSearchResult:
    """A single hybrid search result."""

    id: str
    text: str
    metadata: dict[str, Any]
    semantic_score: float
    keyword_score: float
    hybrid_score: float
    rank: int


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for keyword matching."""
    return [t.lower() for t in re.findall(r"[\w가-힣]+", text) if len(t) > 1]


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Simplified BM25 scoring for a single document."""
    if not query_tokens or not doc_tokens:
        return 0.0

    doc_len = len(doc_tokens)
    tf_map: dict[str, int] = {}
    for t in doc_tokens:
        tf_map[t] = tf_map.get(t, 0) + 1

    score = 0.0
    for qt in query_tokens:
        tf = tf_map.get(qt, 0)
        if tf == 0:
            continue
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += numerator / denominator

    return score


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> dict[str, float]:
    """Reciprocal Rank Fusion across multiple ranked lists.

    Returns {doc_id: fused_score}.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_search(
    query: str,
    documents: list[dict[str, Any]],
    query_embedding: Sequence[float] | None = None,
    top_k: int = 5,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
    use_rrf: bool = True,
) -> list[HybridSearchResult]:
    """Hybrid keyword + semantic search with RRF re-ranking.

    Args:
        query: Search query string.
        documents: List of dicts with at minimum 'id' and 'text'.
            Optionally 'embedding' (list[float]) and 'metadata' (dict).
        query_embedding: Pre-computed query embedding vector.
            If None, only keyword search is used.
        top_k: Number of results to return.
        semantic_weight: Weight for semantic similarity (0-1).
        keyword_weight: Weight for keyword matching (0-1).
        use_rrf: Use Reciprocal Rank Fusion instead of weighted linear combination.

    Returns:
        Sorted list of HybridSearchResult.
    """
    if not documents:
        return []

    query_tokens = _tokenize(query)

    # BM25 keyword scores
    all_doc_tokens = []
    for doc in documents:
        all_doc_tokens.append(_tokenize(doc.get("text", "")))
    avg_doc_len = sum(len(t) for t in all_doc_tokens) / max(len(all_doc_tokens), 1)

    keyword_scores: dict[str, float] = {}
    for doc, doc_tokens in zip(documents, all_doc_tokens, strict=False):
        doc_id = doc["id"]
        keyword_scores[doc_id] = _bm25_score(query_tokens, doc_tokens, avg_doc_len)

    # Semantic scores
    semantic_scores: dict[str, float] = {}
    if query_embedding is not None:
        for doc in documents:
            doc_id = doc["id"]
            doc_emb = doc.get("embedding")
            if doc_emb:
                semantic_scores[doc_id] = _cosine_similarity(query_embedding, doc_emb)
            else:
                semantic_scores[doc_id] = 0.0

    # Combine scores
    if use_rrf and query_embedding is not None:
        # RRF: rank separately then fuse
        kw_ranked = sorted(keyword_scores, key=lambda d: -keyword_scores[d])
        sem_ranked = sorted(semantic_scores, key=lambda d: -semantic_scores[d])
        fused = _reciprocal_rank_fusion([kw_ranked, sem_ranked])
        sorted_ids = sorted(fused, key=lambda d: -fused[d])
    else:
        # Weighted linear combination
        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0
        max_sem = max(semantic_scores.values()) if semantic_scores else 1.0
        combined: dict[str, float] = {}
        for doc in documents:
            doc_id = doc["id"]
            kw_norm = keyword_scores.get(doc_id, 0) / max(max_kw, 1e-9)
            sem_norm = semantic_scores.get(doc_id, 0) / max(max_sem, 1e-9)
            if query_embedding is not None:
                combined[doc_id] = semantic_weight * sem_norm + keyword_weight * kw_norm
            else:
                combined[doc_id] = kw_norm
        sorted_ids = sorted(combined, key=lambda d: -combined[d])

    # Build result objects
    doc_map = {doc["id"]: doc for doc in documents}
    results = []
    for rank, doc_id in enumerate(sorted_ids[:top_k], 1):
        doc = doc_map[doc_id]
        results.append(
            HybridSearchResult(
                id=doc_id,
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                semantic_score=round(semantic_scores.get(doc_id, 0.0), 4),
                keyword_score=round(keyword_scores.get(doc_id, 0.0), 4),
                hybrid_score=round((fused if use_rrf and query_embedding else combined).get(doc_id, 0.0), 4),
                rank=rank,
            )
        )

    return results
