"""
getdaytrends v3.0 - Data Models (Pydantic V2)
모든 모듈에서 사용하는 공유 데이터 구조 정의.
v3.0: ScoredTrend에 sentiment/safety_flag, GeneratedTweet에 variant_id/language 추가.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrendSource(Enum):
    GETDAYTRENDS = "getdaytrends"
    TWITTER = "twitter"
    REDDIT = "reddit"
    GOOGLE_NEWS = "google_news"
    GOOGLE_TRENDS = "google_trends"
    YOUTUBE = "youtube"  # [v5.0] YouTube Trending


class TweetStatus(Enum):
    PENDING = "대기중"
    POSTED = "게시완료"
    SKIPPED = "건너뜀"


class RawTrend(BaseModel):
    """단일 소스에서 수집된 트렌드."""
    name: str
    source: TrendSource
    volume: str = "N/A"
    volume_numeric: int = 0
    link: str = ""
    country: str = "korea"
    extra: dict = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.now)
    published_at: Optional[datetime] = None  # [v6.1] 소스 콘텐츠 발행 시점 (RSS pubDate)


class MultiSourceContext(BaseModel):
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


class ScoredTrend(BaseModel):
    """바이럴 분석 완료된 트렌드."""
    keyword: str
    rank: int
    volume_last_24h: int = 0
    trend_acceleration: str = "+0%"
    viral_potential: int = 0
    top_insight: str = ""
    suggested_angles: list[str] = Field(default_factory=list)
    best_hook_starter: str = ""
    category: str = ""          # 트렌드 카테고리 (연예/스포츠/정치/경제/테크 등)
    context: Optional[MultiSourceContext] = None
    sources: list[TrendSource] = Field(default_factory=list)
    country: str = "korea"
    scored_at: datetime = Field(default_factory=datetime.now)
    # [v3.0] 감성 분석 + 안전 필터
    sentiment: str = "neutral"  # positive | neutral | negative | harmful
    safety_flag: bool = False   # True면 콘텐츠 생성 스킵 (재난/혐오/사망 관련)
    # [v4.0] 트렌드 검증 & 중연 관점 필드
    cross_source_confidence: int = 0    # 0~4: 멀티소스 교차 검증 점수 (볼륨+X+뉴스+Reddit)
    joongyeon_kick: int = 0             # 0~100: 중연 킥 포인트 잠재력 (현상 역설, 관점 반전 정도)
    joongyeon_angle: str = ""           # 중연 스타일 최적 앵글 (한 문장)
    # [v6.1] 최신성 검증
    content_age_hours: float = 0.0      # 콘텐츠 발행~현재 경과 시간
    freshness_grade: str = "unknown"    # fresh | recent | stale | expired | unknown
    # [v8.0] 트렌드 분석 강화 (프롬프트 ①)
    why_trending: str = ""              # 왜 지금 뜨는지 원인 1-2문장 추론
    peak_status: str = ""              # 상승중|정점|하락중
    relevance_score: int = 0           # 1-10: X에서 활발히 논의하기 적합한 정도
    # [v9.0] 벨로시티 + 이머징 트렌드
    velocity: float = 0.0               # 런 간 볼륨 증가율 (B-1)
    is_emerging: bool = False            # 저볼륨 + 고벨로시티 이머징 트렌드 (C-6)


class TrendCluster(BaseModel):
    """의미적으로 유사한 트렌드 그룹."""
    representative: str
    members: list[str] = Field(default_factory=list)
    merged_context: Optional[MultiSourceContext] = None


class GeneratedTweet(BaseModel):
    """생성된 단일 트윗/포스트."""
    tweet_type: str
    content: str
    content_type: str = "short"  # "short" (280자) | "long" (X Premium+) | "threads" (Meta Threads)
    char_count: int = 0
    # [v3.0] A/B 변형 + 멀티언어 지원
    variant_id: str = ""   # A/B 테스트 변형 식별자 (예: "A", "B"). 기본값 빈 문자열(단일 변형)
    language: str = "ko"   # 생성 언어 코드 (예: "ko", "en", "ja")
    # [v8.0] 멘션 메타데이터 (프롬프트 ②)
    best_posting_time: str = ""        # 추천 게시 시간 (예: 오전 8-10시)
    expected_engagement: str = ""      # 높음|보통|낮음
    reasoning: str = ""                # 이 멘션이 효과적인 이유 한 문장

    @model_validator(mode="after")
    def _compute_char_count(self) -> "GeneratedTweet":
        if not self.char_count and self.content:
            self.char_count = len(self.content)
        return self


class GeneratedThread(BaseModel):
    """고바이럴 트렌드용 멀티트윗 쓰레드."""
    tweets: list[str]
    hook: str = ""


class TweetBatch(BaseModel):
    """하나의 트렌드에 대한 전체 생성 결과."""
    topic: str
    tweets: list[GeneratedTweet] = Field(default_factory=list)
    long_posts: list[GeneratedTweet] = Field(default_factory=list)
    threads_posts: list[GeneratedTweet] = Field(default_factory=list)
    thread: Optional[GeneratedThread] = None
    viral_score: int = 0
    language: str = ""          # [v3.0] 멀티언어 배치 언어 코드 (예: "en", "ja"). 기본값 "" = 기본 언어
    generated_at: datetime = Field(default_factory=datetime.now)


class RunResult(BaseModel):
    """파이프라인 실행 결과 요약."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    run_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    country: str = "korea"
    trends_collected: int = 0
    trends_scored: int = 0
    tweets_generated: int = 0
    tweets_saved: int = 0
    alerts_sent: int = 0
    errors: list[str] = Field(default_factory=list)
    # [v6.0] 품질 피드백 메트릭
    avg_qa_score: float = 0.0
    regeneration_count: int = 0
    category_distribution: dict = Field(default_factory=dict)
