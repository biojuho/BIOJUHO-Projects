"""
getdaytrends — Performance Models
성과 추적을 위한 데이터 모델, 상수, 정규화 함수.
performance_tracker.py에서 분리됨.
"""

from dataclasses import dataclass
from datetime import datetime

# ── Data Models ──────────────────────────────────────────

ANGLE_TYPES = ["reversal", "data_punch", "empathy", "tips", "debate"]

# tweet_type(한글) → 정규화된 앵글 키 매핑
_ANGLE_ALIASES: dict[str, str] = {
    # A. 반전
    "반전": "reversal",
    "reversal": "reversal",
    # B. 데이터 펀치
    "데이터 펀치": "data_punch",
    "데이터": "data_punch",
    "data_punch": "data_punch",
    "data punch": "data_punch",
    # C. 공감 자조
    "공감 자조": "empathy",
    "공감": "empathy",
    "공감 유도형": "empathy",
    "empathy": "empathy",
    # D. 꿀팁
    "꿀팁": "tips",
    "꿀팁형": "tips",
    "실용": "tips",
    "tips": "tips",
    # E. 찬반 도발
    "찬반 도발": "debate",
    "찬반": "debate",
    "찬반 질문형": "debate",
    "debate": "debate",
    # 기타 (generator가 자유 생성하는 유형들)
    "딥다이브 분석": "data_punch",
    "핫테이크 오피니언": "reversal",
    "분석형": "data_punch",
    "동기부여형": "empathy",
    "유머/밈형": "empathy",
    "훅 포스트": "reversal",
    "참여형 포스트": "debate",
}


def normalize_angle(tweet_type: str) -> str:
    """tweet_type 문자열을 정규화된 앵글 키로 변환.
    매칭 실패 시 부분 매칭 시도 후 'unknown' 반환.
    """
    if not tweet_type:
        return "unknown"
    key = tweet_type.strip().lower()
    # 정확히 매칭
    if key in _ANGLE_ALIASES:
        return _ANGLE_ALIASES[key]
    # 부분 매칭: 앵글 키워드가 포함되어 있는지 확인
    for alias, angle in _ANGLE_ALIASES.items():
        if alias in key or key in alias:
            return angle
    return "unknown"


@dataclass
class TweetMetrics:
    tweet_id: str
    impressions: int = 0
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    engagement_rate: float = 0.0
    angle_type: str = ""
    hook_pattern: str = ""  # [B] 훅 패턴: number_shock|relatable_math|reversal|insider|contrast|question
    kick_pattern: str = ""  # [B] 킥 패턴: mic_drop|self_deprecation|uncertainty|manifesto|twist
    collected_at: datetime | None = None
    collection_tier: str = ""  # [D] 수집 단계: "1h"|"6h"|"48h"

    def compute_engagement_rate(self) -> float:
        """engagement_rate = (likes + retweets + replies + quotes) / impressions."""
        if self.impressions <= 0:
            self.engagement_rate = 0.0
        else:
            total = self.likes + self.retweets + self.replies + self.quotes
            self.engagement_rate = round(total / self.impressions, 6)
        return self.engagement_rate


@dataclass
class AngleStats:
    angle: str
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0
    weight: float = 0.2  # default equal weight (5 angles)


# [B] 훅/킥 패턴 정규화 매핑
HOOK_PATTERNS = ["number_shock", "relatable_math", "reversal", "insider", "contrast", "question"]
KICK_PATTERNS = ["mic_drop", "self_deprecation", "uncertainty", "manifesto", "twist"]

_HOOK_ALIASES: dict[str, str] = {
    "숫자충격": "number_shock",
    "숫자 충격": "number_shock",
    "number_shock": "number_shock",
    "체감환산": "relatable_math",
    "체감 환산": "relatable_math",
    "relatable_math": "relatable_math",
    "반전선언": "reversal",
    "반전 선언": "reversal",
    "내부자시선": "insider",
    "내부자 시선": "insider",
    "insider": "insider",
    "대조병치": "contrast",
    "대조 병치": "contrast",
    "contrast": "contrast",
    "질문도발": "question",
    "질문 도발": "question",
    "question": "question",
}

_KICK_ALIASES: dict[str, str] = {
    "뒤통수": "mic_drop",
    "mic_drop": "mic_drop",
    "자조형": "self_deprecation",
    "자조": "self_deprecation",
    "self_deprecation": "self_deprecation",
    "질문형": "uncertainty",
    "uncertainty": "uncertainty",
    "선언형": "manifesto",
    "manifesto": "manifesto",
    "반전형": "twist",
    "twist": "twist",
}


def normalize_hook(hook_type: str) -> str:
    """훅 패턴 정규화."""
    if not hook_type:
        return "unknown"
    key = hook_type.strip().lower()
    if key in _HOOK_ALIASES:
        return _HOOK_ALIASES[key]
    for alias, pattern in _HOOK_ALIASES.items():
        if alias in key or key in alias:
            return pattern
    return "unknown"


def normalize_kick(kick_type: str) -> str:
    """킥 패턴 정규화."""
    if not kick_type:
        return "unknown"
    key = kick_type.strip().lower()
    if key in _KICK_ALIASES:
        return _KICK_ALIASES[key]
    for alias, pattern in _KICK_ALIASES.items():
        if alias in key or key in alias:
            return pattern
    return "unknown"


@dataclass
class PatternStats:
    """[B] 훅/킥 패턴별 성과 통계."""

    pattern: str
    pattern_type: str  # "hook" | "kick"
    total_tweets: int = 0
    avg_impressions: float = 0.0
    avg_engagement_rate: float = 0.0
    weight: float = 0.0


@dataclass
class GoldenReference:
    """[E] 골든 레퍼런스 — 고성과 트윗을 QA 벤치마크로 저장."""

    tweet_id: str
    content: str
    angle_type: str
    hook_pattern: str
    kick_pattern: str
    engagement_rate: float
    impressions: int
    category: str = ""
    saved_at: datetime | None = None
