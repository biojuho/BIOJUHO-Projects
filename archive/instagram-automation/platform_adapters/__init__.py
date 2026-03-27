"""Platform adapter base class.

Abstract interface for multi-platform social media publishing.
Inspired by frankomondo/ai-social-media-post-automation adapter pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PostContent:
    """Platform-agnostic content to publish."""

    caption: str
    image_url: str | None = None
    video_url: str | None = None
    hashtags: list[str] = field(default_factory=list)
    post_type: str = "IMAGE"  # IMAGE, REEL, CAROUSEL, STORY
    carousel_urls: list[str] = field(default_factory=list)
    scheduled_time: datetime | None = None

    @property
    def full_caption(self) -> str:
        """Caption with hashtags appended."""
        parts = [self.caption]
        if self.hashtags:
            parts.append("\n\n" + " ".join(self.hashtags))
        return "".join(parts)


@dataclass
class PublishResult:
    """Result from publishing a post."""

    platform: str
    post_id: str
    url: str = ""
    success: bool = True
    error: str = ""


class PlatformAdapter(ABC):
    """Abstract base for platform adapters."""

    platform_name: str = "unknown"

    @abstractmethod
    async def authenticate(self) -> bool:
        """Verify authentication is valid. Returns True if OK."""
        ...

    @abstractmethod
    async def publish(self, content: PostContent) -> PublishResult:
        """Publish content to the platform."""
        ...

    @abstractmethod
    async def get_insights(self, post_id: str) -> dict:
        """Get performance metrics for a published post."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        ...
