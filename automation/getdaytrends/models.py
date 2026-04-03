"""
getdaytrends data models.

This module keeps the existing pipeline models stable while adding the V2.0
workflow contracts used by the review queue, manual publish loop, and feedback
summary tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrendSource(Enum):
    GETDAYTRENDS = "getdaytrends"
    TWITTER = "twitter"
    REDDIT = "reddit"
    GOOGLE_NEWS = "google_news"
    GOOGLE_TRENDS = "google_trends"
    YOUTUBE = "youtube"


class TweetStatus(Enum):
    PENDING = "대기중"
    POSTED = "게시완료"
    SKIPPED = "건너뜀"


class WorkflowLifecycleStatus(str, Enum):
    COLLECTED = "collected"
    VALIDATED = "validated"
    SCORED = "scored"
    DRAFTED = "drafted"
    READY = "ready"
    APPROVED = "approved"
    PUBLISHED = "published"
    MEASURED = "measured"
    LEARNED = "learned"


class ReviewQueueStatus(str, Enum):
    DRAFT = "Draft"
    READY = "Ready"
    APPROVED = "Approved"
    PUBLISHED = "Published"
    REJECTED = "Rejected"
    EXPIRED = "Expired"


class RawTrend(BaseModel):
    """One raw trend collected from an upstream source."""

    name: str
    source: TrendSource
    volume: str = "N/A"
    volume_numeric: int = 0
    link: str = ""
    country: str = "korea"
    extra: dict = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.now)
    published_at: datetime | None = None


class TrendContext(BaseModel):
    """Structured context explaining why the trend is happening now."""

    trigger_event: str = ""
    chain_reaction: str = ""
    why_now: str = ""
    key_positions: list[str] = Field(default_factory=list)
    real_tweets_summary: str = ""

    def to_prompt_text(self) -> str:
        parts: list[str] = []
        if self.trigger_event:
            parts.append(f"[Trigger] {self.trigger_event}")
        if self.chain_reaction:
            parts.append(f"[Chain Reaction] {self.chain_reaction}")
        if self.why_now:
            parts.append(f"[Why Now] {self.why_now}")
        if self.key_positions:
            parts.append(f"[Key Positions] {' / '.join(self.key_positions)}")
        if self.real_tweets_summary:
            parts.append(f"[Live Reactions] {self.real_tweets_summary}")
        return "\n".join(parts)


class MultiSourceContext(BaseModel):
    """Source-specific context merged for one keyword."""

    twitter_insight: str = ""
    reddit_insight: str = ""
    news_insight: str = ""

    def to_combined_text(self) -> str:
        sections: list[str] = []
        if self.twitter_insight:
            sections.append(f"[X 실시간 반응]\n{self.twitter_insight}")
        if self.reddit_insight:
            sections.append(f"[Reddit 커뮤니티]\n{self.reddit_insight}")
        if self.news_insight:
            sections.append(f"[뉴스 헤드라인]\n{self.news_insight}")
        return "\n\n".join(sections)


class ScoredTrend(BaseModel):
    """Trend after scoring and quality checks."""

    keyword: str
    rank: int
    volume_last_24h: int = 0
    trend_acceleration: str = "+0%"
    viral_potential: int = 0
    top_insight: str = ""
    suggested_angles: list[str] = Field(default_factory=list)
    best_hook_starter: str = ""
    category: str = ""
    context: MultiSourceContext | None = None
    sources: list[TrendSource] = Field(default_factory=list)
    country: str = "korea"
    scored_at: datetime = Field(default_factory=datetime.now)
    sentiment: str = "neutral"
    safety_flag: bool = False
    cross_source_confidence: int = 0
    joongyeon_kick: int = 0
    joongyeon_angle: str = ""
    content_age_hours: float = 0.0
    freshness_grade: str = "unknown"
    why_trending: str = ""
    peak_status: str = ""
    relevance_score: int = 0
    trend_context: TrendContext | None = None
    velocity: float = 0.0
    is_emerging: bool = False
    publishable: bool = True
    publishability_reason: str = ""
    corrected_keyword: str = ""
    parent_trends: list[str] = Field(default_factory=list)
    predicted_children: list[str] = Field(default_factory=list)
    genealogy_depth: int = 0
    source_credibility: float = 0.0
    fact_check_score: float = 1.0
    hallucination_flags: list[str] = Field(default_factory=list)
    cross_source_consistent: bool = True
    cross_source_agreement: float = 0.5


class TrendCluster(BaseModel):
    """Cluster of semantically similar trends."""

    representative: str
    members: list[str] = Field(default_factory=list)
    merged_context: MultiSourceContext | None = None


class GeneratedTweet(BaseModel):
    """One generated content unit."""

    tweet_type: str
    content: str
    content_type: str = "short"
    char_count: int = 0
    variant_id: str = ""
    language: str = "ko"
    best_posting_time: str = ""
    expected_engagement: str = ""
    reasoning: str = ""
    platform: str = "x"
    seo_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_char_count(self) -> "GeneratedTweet":
        if not self.char_count and self.content:
            self.char_count = len(self.content)
        return self


class GeneratedThread(BaseModel):
    """Thread representation for multi-post content."""

    tweets: list[str]
    hook: str = ""


class TweetBatch(BaseModel):
    """All generated outputs for one trend."""

    topic: str
    tweets: list[GeneratedTweet] = Field(default_factory=list)
    long_posts: list[GeneratedTweet] = Field(default_factory=list)
    threads_posts: list[GeneratedTweet] = Field(default_factory=list)
    blog_posts: list[GeneratedTweet] = Field(default_factory=list)
    thread: GeneratedThread | None = None
    viral_score: int = 0
    language: str = ""
    metadata: dict = Field(default_factory=dict)
    visual_urls: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class ValidatedTrend(BaseModel):
    """V2.0 validated trend contract for downstream workflow steps."""

    trend_id: str
    keyword: str
    confidence_score: float = 0.0
    source_count: int = 0
    evidence_refs: list[str] = Field(default_factory=list)
    freshness_minutes: int = 0
    dedup_fingerprint: str = ""
    lifecycle_status: WorkflowLifecycleStatus = WorkflowLifecycleStatus.VALIDATED
    scoring_axes: dict[str, float] = Field(default_factory=dict)
    scoring_reasons: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class DraftBundle(BaseModel):
    """V2.0 publish-ready draft contract."""

    draft_id: str
    trend_id: str
    platform: str
    content_type: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    prompt_version: str = ""
    generator_provider: str = ""
    generator_model: str = ""
    source_evidence_ref: str = ""
    degraded_mode: bool = False
    lifecycle_status: WorkflowLifecycleStatus = WorkflowLifecycleStatus.DRAFTED
    review_status: ReviewQueueStatus = ReviewQueueStatus.DRAFT
    notion_page_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class QAReport(BaseModel):
    """V2.0 QA gate output for one draft bundle."""

    draft_id: str
    total_score: float = 0.0
    passed: bool = False
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ReviewDecision(BaseModel):
    """Manual review decision captured from the canonical queue."""

    draft_id: str
    decision: str
    reviewed_by: str = ""
    reviewed_at: datetime = Field(default_factory=datetime.now)
    review_note: str = ""


class PublishReceipt(BaseModel):
    """Receipt recorded after a manual external publish."""

    draft_id: str
    platform: str
    success: bool = False
    published_url: str = ""
    published_at: datetime | None = None
    failure_code: str = ""
    failure_reason: str = ""
    receipt_id: str = ""


class FeedbackSummary(BaseModel):
    """Closed-loop feedback summary linked to a publish receipt."""

    draft_id: str
    metric_window: str = ""
    impressions: int = 0
    engagements: int = 0
    clicks: int = 0
    collector_status: str = ""
    strategy_notes: str = ""
    receipt_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class RunResult(BaseModel):
    """Pipeline run result summary."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    country: str = "korea"
    trends_collected: int = 0
    trends_scored: int = 0
    tweets_generated: int = 0
    tweets_saved: int = 0
    alerts_sent: int = 0
    errors: list[str] = Field(default_factory=list)
    avg_qa_score: float = 0.0
    regeneration_count: int = 0
    category_distribution: dict = Field(default_factory=dict)
