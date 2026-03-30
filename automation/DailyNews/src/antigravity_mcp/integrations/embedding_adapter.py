"""Embedding-based article clustering adapter.

Uses Google Gemini Embedding API to compute article embeddings and
clusters similar articles into topic groups using cosine similarity.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import httpx

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentItem

logger = logging.getLogger(__name__)

# Similarity threshold for merging articles into the same cluster
_DEFAULT_SIMILARITY_THRESHOLD = 0.75
_EMBEDDING_MODEL = "models/gemini-embedding-001"


@dataclass
class ArticleCluster:
    """A group of semantically similar articles about the same topic."""

    cluster_id: int
    topic_label: str  # derived from the first article's title
    articles: list[ContentItem] = field(default_factory=list)
    source_count: int = 0  # number of distinct sources covering this topic

    @property
    def is_multi_source(self) -> bool:
        return self.source_count > 1


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingAdapter:
    """Computes embeddings via Google Gemini and clusters articles by similarity."""

    def __init__(self, *, similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD) -> None:
        self.settings = get_settings()
        self.similarity_threshold = similarity_threshold
        self._api_key = self.settings.google_api_key

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Fetch embeddings for a batch of texts using Gemini Embedding API."""
        if not self._api_key:
            raise RuntimeError("GOOGLE_API_KEY not configured for embeddings.")

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
        requests_body = [
            {
                "model": _EMBEDDING_MODEL,
                "taskType": "CLUSTERING",
                "content": {"parts": [{"text": t[:2048]}]},
            }
            for t in texts
        ]
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json={"requests": requests_body})
            resp.raise_for_status()
            data = resp.json()
        return [item["values"] for item in data["embeddings"]]

    async def cluster_articles(
        self,
        articles: list[ContentItem],
    ) -> list[ArticleCluster]:
        """Cluster articles by semantic similarity of their titles + summaries."""
        if not articles:
            return []
        if not self.is_available:
            # No API key: return each article as its own cluster
            return [
                ArticleCluster(
                    cluster_id=i,
                    topic_label=a.title,
                    articles=[a],
                    source_count=1,
                )
                for i, a in enumerate(articles)
            ]

        texts = [f"{a.title}. {a.summary[:200]}" for a in articles]
        try:
            embeddings = await self.get_embeddings(texts)
        except Exception as exc:
            logger.warning("Embedding API failed, skipping clustering: %s", exc)
            return [
                ArticleCluster(cluster_id=i, topic_label=a.title, articles=[a], source_count=1)
                for i, a in enumerate(articles)
            ]

        # Greedy clustering: assign each article to the first matching cluster
        clusters: list[ArticleCluster] = []
        cluster_centroids: list[list[float]] = []
        assigned: list[int] = [-1] * len(articles)

        for i, emb in enumerate(embeddings):
            best_cluster = -1
            best_sim = 0.0
            for ci, centroid in enumerate(cluster_centroids):
                sim = _cosine_similarity(emb, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_cluster = ci

            if best_sim >= self.similarity_threshold and best_cluster >= 0:
                assigned[i] = best_cluster
                clusters[best_cluster].articles.append(articles[i])
            else:
                # New cluster
                assigned[i] = len(clusters)
                clusters.append(
                    ArticleCluster(
                        cluster_id=len(clusters),
                        topic_label=articles[i].title,
                        articles=[articles[i]],
                    )
                )
                cluster_centroids.append(emb)

        # Compute source_count per cluster
        for cluster in clusters:
            cluster.source_count = len({a.source_name for a in cluster.articles})

        # Sort: multi-source clusters first, then by article count desc
        clusters.sort(key=lambda c: (-c.source_count, -len(c.articles)))
        return clusters
