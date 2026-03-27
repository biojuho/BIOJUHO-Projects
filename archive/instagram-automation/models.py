"""Pydantic models for Instagram automation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------- Enums ----------


class PostType(str, Enum):
    IMAGE = "IMAGE"
    REELS = "REELS"
    STORIES = "STORIES"
    CAROUSEL_ALBUM = "CAROUSEL_ALBUM"


class PostStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class ContainerStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


# ---------- Content ----------


class InstagramPost(BaseModel):
    """A single Instagram post ready for publishing."""

    id: int | None = None
    caption: str = ""
    hashtags: str = ""
    image_url: str | None = None  # public direct URL
    video_url: str | None = None
    carousel_urls: list[str] = Field(default_factory=list)
    post_type: PostType = PostType.IMAGE
    status: PostStatus = PostStatus.DRAFT
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    media_id: str | None = None  # IG media ID after publishing
    container_id: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def full_caption(self) -> str:
        parts = [self.caption]
        if self.hashtags:
            parts.append("")
            parts.append(self.hashtags)
        return "\n".join(parts)


# ---------- DM / Comments ----------


class DMTriggerRule(BaseModel):
    """Keyword-triggered auto-DM rule."""

    keyword: str
    response_template: str
    is_llm_response: bool = False  # use LLM to generate response
    enabled: bool = True


class WebhookEvent(BaseModel):
    """Parsed Meta webhook event."""

    event_type: str  # "comments" | "messages" | "mentions"
    sender_id: str
    text: str = ""
    media_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    raw: dict = Field(default_factory=dict)


# ---------- Analytics ----------


class PostInsights(BaseModel):
    """Performance metrics for a published post."""

    media_id: str
    impressions: int = 0
    reach: int = 0
    engagement: int = 0
    likes: int = 0
    comments: int = 0
    saved: int = 0
    shares: int = 0
    collected_at: datetime = Field(default_factory=datetime.now)

    @property
    def engagement_rate(self) -> float:
        if self.reach == 0:
            return 0.0
        return (self.engagement / self.reach) * 100


# ---------- API Responses ----------


class MediaContainerResponse(BaseModel):
    """Meta API media container response."""

    id: str


class PublishResponse(BaseModel):
    """Meta API publish response."""

    id: str  # media ID
