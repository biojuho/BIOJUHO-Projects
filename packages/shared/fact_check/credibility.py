"""Source credibility scoring for news outlets."""

from __future__ import annotations

import re
from enum import Enum


class CredibilityTier(Enum):
    TIER_1 = "tier_1"  # Wire services / public broadcasting
    TIER_2 = "tier_2"  # Major newspapers / specialist outlets
    TIER_3 = "tier_3"  # Online media / portals
    TIER_4 = "tier_4"  # Blogs / communities / unverified
    UNKNOWN = "unknown"


_SOURCE_CREDIBILITY_MAP: dict[str, CredibilityTier] = {
    # Tier 1
    "연합뉴스": CredibilityTier.TIER_1,
    "yonhapnews": CredibilityTier.TIER_1,
    "kbs": CredibilityTier.TIER_1,
    "mbc": CredibilityTier.TIER_1,
    "sbs": CredibilityTier.TIER_1,
    "bbc": CredibilityTier.TIER_1,
    "reuters": CredibilityTier.TIER_1,
    "ap news": CredibilityTier.TIER_1,
    "associated press": CredibilityTier.TIER_1,
    "nhk": CredibilityTier.TIER_1,
    "afp": CredibilityTier.TIER_1,
    # Tier 2
    "조선일보": CredibilityTier.TIER_2,
    "중앙일보": CredibilityTier.TIER_2,
    "동아일보": CredibilityTier.TIER_2,
    "한겨레": CredibilityTier.TIER_2,
    "경향신문": CredibilityTier.TIER_2,
    "한국경제": CredibilityTier.TIER_2,
    "매일경제": CredibilityTier.TIER_2,
    "jtbc": CredibilityTier.TIER_2,
    "bloomberg": CredibilityTier.TIER_2,
    "wsj": CredibilityTier.TIER_2,
    "wall street journal": CredibilityTier.TIER_2,
    "nytimes": CredibilityTier.TIER_2,
    "new york times": CredibilityTier.TIER_2,
    "washington post": CredibilityTier.TIER_2,
    "financial times": CredibilityTier.TIER_2,
    "cnbc": CredibilityTier.TIER_2,
    "nikkei": CredibilityTier.TIER_2,
    # Tier 3
    "머니투데이": CredibilityTier.TIER_3,
    "뉴시스": CredibilityTier.TIER_3,
    "뉴스1": CredibilityTier.TIER_3,
    "이데일리": CredibilityTier.TIER_3,
    "서울경제": CredibilityTier.TIER_3,
    "아시아경제": CredibilityTier.TIER_3,
    "허프포스트": CredibilityTier.TIER_3,
    "huffpost": CredibilityTier.TIER_3,
    "the verge": CredibilityTier.TIER_3,
    "techcrunch": CredibilityTier.TIER_3,
    "wired": CredibilityTier.TIER_3,
}

_CREDIBILITY_WEIGHTS: dict[CredibilityTier, float] = {
    CredibilityTier.TIER_1: 1.0,
    CredibilityTier.TIER_2: 0.8,
    CredibilityTier.TIER_3: 0.6,
    CredibilityTier.TIER_4: 0.3,
    CredibilityTier.UNKNOWN: 0.4,
}


def get_source_credibility(source_text: str) -> CredibilityTier:
    """Determine credibility tier from source text."""
    if not source_text:
        return CredibilityTier.UNKNOWN
    lower = source_text.lower()
    for pattern, tier in _SOURCE_CREDIBILITY_MAP.items():
        if pattern.lower() in lower:
            return tier
    return CredibilityTier.TIER_4


def compute_source_credibility_score(news_insight: str) -> float:
    """Compute weighted average credibility score (0.0~1.0) from news insight text."""
    if not news_insight or len(news_insight) < 10:
        return 0.0

    tiers_found: list[CredibilityTier] = []
    segments = re.split(r"\s*\|\s*", news_insight)
    for seg in segments:
        tier = get_source_credibility(seg)
        if tier != CredibilityTier.UNKNOWN:
            tiers_found.append(tier)

    if not tiers_found:
        tier = get_source_credibility(news_insight)
        tiers_found.append(tier)

    if not tiers_found:
        return 0.4

    weights = [_CREDIBILITY_WEIGHTS[t] for t in tiers_found]
    return round(sum(weights) / len(weights), 2)
