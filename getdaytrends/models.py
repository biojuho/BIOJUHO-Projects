"""
getdaytrends v2.0 - Data Models
모든 모듈에서 사용하는 공유 데이터 구조 정의.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TrendSource(Enum):
    GETDAYTRENDS = "getdaytrends"
    TWITTER = "twitter"
    REDDIT = "reddit"
    GOOGLE_NEWS = "google_news"


class TweetStatus(Enum):
    PENDING = "대기중"
    POSTED = "게시완료"
    SKIPPED = "건너뜀"


@dataclass
class RawTrend:
    """단일 소스에서 수집된 트렌드."""
    name: str
    source: TrendSource
    volume: str = "N/A"
    volume_numeric: int = 0
    link: str = ""
    country: str = "korea"
    extra: dict = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class MultiSourceContext:
    """하나의 키워드에 대한 멀티소스 컨텍스트."""
    twitter_insight: str = ""
    reddit_insight: str = ""
    news_insight: str = ""

    def to_combined_text(self) -> str:
        sections = []
        if self.twitter_insight:
            sections.append(f"[X 실시간 반응]\n{self.twitter_insight}")
        if self.reddit_insight:
            sections.append(f"[Reddit 커뮤니티]\n{self.reddit_insight}")
        if self.news_insight:
            sections.append(f"[뉴스 헤드라인]\n{self.news_insight}")
        return "\n\n".join(sections)


@dataclass
class ScoredTrend:
    """바이럴 분석 완료된 트렌드."""
    keyword: str
    rank: int
    volume_last_24h: int = 0
    trend_acceleration: str = "+0%"
    viral_potential: int = 0
    top_insight: str = ""
    suggested_angles: list[str] = field(default_factory=list)
    best_hook_starter: str = ""
    context: Optional[MultiSourceContext] = None
    sources: list[TrendSource] = field(default_factory=list)
    country: str = "korea"
    scored_at: datetime = field(default_factory=datetime.now)


@dataclass
class GeneratedTweet:
    """생성된 단일 트윗."""
    tweet_type: str
    content: str
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)


@dataclass
class GeneratedThread:
    """고바이럴 트렌드용 멀티트윗 쓰레드."""
    tweets: list[str]
    hook: str = ""


@dataclass
class TweetBatch:
    """하나의 트렌드에 대한 전체 생성 결과."""
    topic: str
    tweets: list[GeneratedTweet] = field(default_factory=list)
    thread: Optional[GeneratedThread] = None
    viral_score: int = 0
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RunResult:
    """파이프라인 실행 결과 요약."""
    run_id: str
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    country: str = "korea"
    trends_collected: int = 0
    trends_scored: int = 0
    tweets_generated: int = 0
    tweets_saved: int = 0
    alerts_sent: int = 0
    errors: list[str] = field(default_factory=list)
