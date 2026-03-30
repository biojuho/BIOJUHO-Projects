"""
getdaytrends — Source Credibility
뉴스 출처 신뢰도 등급 판별 및 점수 산출.
fact_checker.py에서 분리됨.
"""

import re
from enum import Enum

# ══════════════════════════════════════════════════════
#  Source Credibility Tiers
# ══════════════════════════════════════════════════════


class CredibilityTier(Enum):
    """뉴스 출처 신뢰도 등급."""

    TIER_1 = "tier_1"  # 주요 통신사/공영방송 (연합뉴스, KBS, BBC, Reuters, AP)
    TIER_2 = "tier_2"  # 종합일간지/전문지 (조선일보, 한겨레, Bloomberg, WSJ)
    TIER_3 = "tier_3"  # 인터넷 매체/포털 (허프포스트, 매일경제 등)
    TIER_4 = "tier_4"  # 블로그/커뮤니티/미확인 출처
    UNKNOWN = "unknown"


# 출처명 패턴 → 신뢰도 등급 매핑
_SOURCE_CREDIBILITY_MAP: dict[str, CredibilityTier] = {
    # Tier 1: 통신사 & 공영방송
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
    # Tier 2: 종합일간지 & 전문지
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
    # Tier 3: 인터넷 매체
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

# 신뢰도 등급별 가중치 (cross_source_confidence 계산에 사용)
_CREDIBILITY_WEIGHTS: dict[CredibilityTier, float] = {
    CredibilityTier.TIER_1: 1.0,
    CredibilityTier.TIER_2: 0.8,
    CredibilityTier.TIER_3: 0.6,
    CredibilityTier.TIER_4: 0.3,
    CredibilityTier.UNKNOWN: 0.4,
}


def get_source_credibility(source_text: str) -> CredibilityTier:
    """출처 텍스트에서 신뢰도 등급 판별."""
    if not source_text:
        return CredibilityTier.UNKNOWN
    lower = source_text.lower()
    for pattern, tier in _SOURCE_CREDIBILITY_MAP.items():
        if pattern.lower() in lower:
            return tier
    return CredibilityTier.TIER_4


def compute_source_credibility_score(news_insight: str) -> float:
    """
    뉴스 인사이트 텍스트에서 출처 신뢰도 점수 산출 (0.0~1.0).
    여러 출처가 있으면 가중 평균.
    """
    if not news_insight or len(news_insight) < 10:
        return 0.0

    tiers_found: list[CredibilityTier] = []

    # 헤드라인 구분자 기반 출처 탐색
    segments = re.split(r"\s*\|\s*", news_insight)
    for seg in segments:
        tier = get_source_credibility(seg)
        if tier != CredibilityTier.UNKNOWN:
            tiers_found.append(tier)

    # 출처 미발견 시 전체 텍스트 검사
    if not tiers_found:
        tier = get_source_credibility(news_insight)
        tiers_found.append(tier)

    if not tiers_found:
        return 0.4  # 기본값

    weights = [_CREDIBILITY_WEIGHTS[t] for t in tiers_found]
    return round(sum(weights) / len(weights), 2)
