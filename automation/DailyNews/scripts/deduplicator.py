"""Smart deduplication for DailyNews.

Detects near-duplicate articles using title similarity
so the same news story from multiple sources is merged.

Uses difflib SequenceMatcher (stdlib, zero dependencies).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ArticleItem:
    """Lightweight article representation for dedup."""

    title: str = ""
    link: str = ""
    source: str = ""
    description: str = ""
    category: str = ""
    score: float = 0.0  # credibility score (0-10)

    @property
    def info_density(self) -> int:
        """Heuristic for information richness."""
        return len(self.title) + len(self.description)


@dataclass
class DedupGroup:
    """A group of near-duplicate articles."""

    canonical: ArticleItem  # best representative
    duplicates: list[ArticleItem] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    @property
    def source_count(self) -> int:
        return len(self.sources)


class NewsDeduplicator:
    """Detect and merge duplicate news articles.

    Uses title similarity via SequenceMatcher.
    Threshold: 0.85 (85% similar → considered duplicate).
    """

    DEFAULT_THRESHOLD = 0.85

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

    def compute_similarity(self, title_a: str, title_b: str) -> float:
        """Compute string similarity between two titles.

        Returns float 0.0~1.0. Uses SequenceMatcher ratio.
        """
        if not title_a or not title_b:
            return 0.0
        # Normalize: lowercase, strip whitespace
        a = title_a.strip().lower()
        b = title_b.strip().lower()
        if a == b:
            return 1.0
        return SequenceMatcher(None, a, b).ratio()

    def find_duplicates(self, articles: list[ArticleItem]) -> list[DedupGroup]:
        """Group articles by similarity.

        Returns list of DedupGroup, each containing near-duplicate articles.
        Articles not matching any group are returned as single-item groups.
        """
        if not articles:
            return []

        used = set()
        groups: list[DedupGroup] = []

        for i, article_a in enumerate(articles):
            if i in used:
                continue

            group_items = [article_a]
            used.add(i)

            for j, article_b in enumerate(articles):
                if j in used:
                    continue
                sim = self.compute_similarity(article_a.title, article_b.title)
                if sim >= self.threshold:
                    group_items.append(article_b)
                    used.add(j)

            # Select canonical (highest info density)
            canonical = max(group_items, key=lambda a: a.info_density)
            duplicates = [a for a in group_items if a is not canonical]
            sources = list({a.source for a in group_items if a.source})

            groups.append(
                DedupGroup(
                    canonical=canonical,
                    duplicates=duplicates,
                    sources=sources,
                )
            )

        dup_count = sum(len(g.duplicates) for g in groups)
        if dup_count > 0:
            logger.info(
                "Dedup: %d articles → %d unique (%d duplicates removed)",
                len(articles),
                len(groups),
                dup_count,
            )

        return groups

    def deduplicate(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convenience: takes raw dicts, returns deduplicated dicts.

        Each dict should have 'title', 'link', 'source', 'description' keys.
        """
        items = [
            ArticleItem(
                title=a.get("title", ""),
                link=a.get("link", ""),
                source=a.get("source", ""),
                description=a.get("description", ""),
                category=a.get("category", ""),
            )
            for a in articles
        ]

        groups = self.find_duplicates(items)

        result = []
        for group in groups:
            c = group.canonical
            entry = {
                "title": c.title,
                "link": c.link,
                "source": c.source,
                "description": c.description,
                "category": c.category,
                "source_count": group.source_count,
                "all_sources": group.sources,
            }
            result.append(entry)

        return result
