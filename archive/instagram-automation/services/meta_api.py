"""Meta Graph API client for Instagram Business Account.

Handles media publishing (image, reel, carousel, story), DM sending,
comment management, and Insights collection via the official Graph API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from config import MetaAPIConfig
from services.rate_limiter import MetaRateLimiter

logger = logging.getLogger(__name__)


class MetaAPIError(Exception):
    """Base Meta Graph API error."""

    def __init__(
        self,
        message: str,
        code: int = 0,
        subcode: int = 0,
        fbtrace_id: str = "",
    ):
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)


class MetaAuthError(MetaAPIError):
    """Invalid or expired access token (code 190)."""


class MetaRateLimitError(MetaAPIError):
    """Rate limit exceeded (codes 4, 17, 32)."""


class MetaPermissionError(MetaAPIError):
    """Insufficient permissions (codes 10, 200)."""


class MetaNotFoundError(MetaAPIError):
    """Resource not found (code 803)."""


class MetaServerError(MetaAPIError):
    """Instagram server error (5xx)."""


class MetaContainerError(MetaAPIError):
    """Container processing failure."""


class ContainerStatus:
    """Container processing status values."""

    EXPIRED = "EXPIRED"
    ERROR = "ERROR"
    FINISHED = "FINISHED"
    IN_PROGRESS = "IN_PROGRESS"


class MetaGraphAPI:
    """Async client for Meta Graph API (Instagram)."""

    def __init__(self, config: MetaAPIConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._call_count = 0
        self._rate_limiter = MetaRateLimiter()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_url,
                timeout=60.0,
                params={"access_token": self.config.access_token},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ---- low-level ----

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict:
        # Enforce Meta's 200 calls/hour rate limit
        await self._rate_limiter.acquire()

        client = await self._get_client()
        self._call_count += 1
        if self._call_count % 50 == 0:
            stats = self._rate_limiter.get_stats()
            logger.info(
                "API call #%d (rate: %d/%d, %.0f%%)",
                self._call_count,
                stats["calls_in_window"],
                stats["effective_limit"],
                stats["usage_pct"],
            )

        resp = await client.request(method, path, **kwargs)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            code = err.get("code", 0)
            subcode = err.get("error_subcode", 0)
            message = err.get("message", "Unknown error")
            fbtrace_id = err.get("fbtrace_id", "")
            kwargs = dict(
                message=message, code=code,
                subcode=subcode, fbtrace_id=fbtrace_id,
            )

            # Classify by error code
            if code == 190:
                raise MetaAuthError(**kwargs)
            if code in (4, 17, 32):
                raise MetaRateLimitError(**kwargs)
            if code in (10, 200):
                raise MetaPermissionError(**kwargs)
            if code == 803:
                raise MetaNotFoundError(**kwargs)
            if resp.status_code >= 500:
                raise MetaServerError(**kwargs)
            raise MetaAPIError(**kwargs)
        return data

    async def get(self, path: str, **params: Any) -> dict:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, **data: Any) -> dict:
        return await self._request("POST", path, data=data)

    # ---- Account info ----

    async def get_account_info(self) -> dict:
        """Get Instagram Business Account info."""
        return await self.get(
            f"/{self.config.ig_user_id}",
            fields="id,username,name,biography,followers_count,follows_count,media_count",
        )

    # ---- Media Publishing (2-step process) ----

    async def create_image_container(
        self, image_url: str, caption: str
    ) -> str:
        """Step 1: Create image media container. Returns container ID."""
        data = await self.post(
            f"/{self.config.ig_user_id}/media",
            image_url=image_url,
            caption=caption,
        )
        container_id = data["id"]
        logger.info("Created image container: %s", container_id)
        return container_id

    async def create_reel_container(
        self, video_url: str, caption: str, *, share_to_feed: bool = True
    ) -> str:
        """Step 1: Create reels media container."""
        data = await self.post(
            f"/{self.config.ig_user_id}/media",
            video_url=video_url,
            caption=caption,
            media_type="REELS",
            share_to_feed=str(share_to_feed).lower(),
        )
        container_id = data["id"]
        logger.info("Created reel container: %s", container_id)
        return container_id

    async def create_story_container(
        self, *, image_url: str | None = None, video_url: str | None = None
    ) -> str:
        """Step 1: Create stories media container."""
        kwargs: dict[str, str] = {"media_type": "STORIES"}
        if image_url:
            kwargs["image_url"] = image_url
        elif video_url:
            kwargs["video_url"] = video_url
        else:
            raise ValueError("image_url or video_url required for stories")

        data = await self.post(
            f"/{self.config.ig_user_id}/media", **kwargs
        )
        return data["id"]

    async def create_carousel_item(self, image_url: str) -> str:
        """Create a single carousel item container (no caption)."""
        data = await self.post(
            f"/{self.config.ig_user_id}/media",
            image_url=image_url,
            is_carousel_item="true",
        )
        return data["id"]

    async def create_carousel_container(
        self, children_ids: list[str], caption: str
    ) -> str:
        """Create carousel album container from child IDs."""
        data = await self.post(
            f"/{self.config.ig_user_id}/media",
            media_type="CAROUSEL_ALBUM",
            caption=caption,
            children=",".join(children_ids),
        )
        return data["id"]

    async def check_container_status(self, container_id: str) -> str:
        """Check if media container is ready for publishing."""
        data = await self.get(
            f"/{container_id}",
            fields="status_code,status",
        )
        return data.get("status_code", "UNKNOWN")

    async def wait_for_container(
        self,
        container_id: str,
        *,
        timeout: int = 300,
        initial_interval: float = 3.0,
        max_interval: float = 15.0,
        backoff_factor: float = 1.5,
    ) -> None:
        """Poll container status with exponential backoff until FINISHED."""
        elapsed = 0.0
        interval = initial_interval
        while elapsed < timeout:
            status = await self.check_container_status(container_id)
            if status == ContainerStatus.FINISHED:
                logger.info("Container %s ready (%.1fs)", container_id, elapsed)
                return
            if status == ContainerStatus.ERROR:
                raise MetaContainerError(
                    f"Container {container_id} failed processing"
                )
            if status == ContainerStatus.EXPIRED:
                raise MetaContainerError(
                    f"Container {container_id} expired (24h TTL)"
                )
            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * backoff_factor, max_interval)
        raise MetaContainerError(
            f"Container {container_id} timed out after {timeout}s"
        )

    async def publish_container(self, container_id: str) -> str:
        """Step 2: Publish a ready container. Returns media ID."""
        data = await self.post(
            f"/{self.config.ig_user_id}/media_publish",
            creation_id=container_id,
        )
        media_id = data["id"]
        logger.info("Published media: %s", media_id)
        return media_id

    # ---- High-level publish helpers ----

    async def publish_image(self, image_url: str, caption: str) -> str:
        """Publish single image post. Returns media ID."""
        container_id = await self.create_image_container(image_url, caption)
        await self.wait_for_container(container_id, timeout=60)
        return await self.publish_container(container_id)

    async def publish_reel(self, video_url: str, caption: str) -> str:
        """Publish reel. Returns media ID."""
        container_id = await self.create_reel_container(video_url, caption)
        await self.wait_for_container(container_id, timeout=300)
        return await self.publish_container(container_id)

    async def publish_carousel(
        self, image_urls: list[str], caption: str
    ) -> str:
        """Publish carousel album (2-10 images). Returns media ID."""
        if len(image_urls) < 2 or len(image_urls) > 10:
            raise ValueError("Carousel requires 2-10 images")
        child_ids = []
        for url in image_urls:
            child_id = await self.create_carousel_item(url)
            child_ids.append(child_id)
        container_id = await self.create_carousel_container(child_ids, caption)
        await self.wait_for_container(container_id, timeout=120)
        return await self.publish_container(container_id)

    async def publish_story(
        self, *, image_url: str | None = None, video_url: str | None = None
    ) -> str:
        """Publish story. Returns media ID."""
        container_id = await self.create_story_container(
            image_url=image_url, video_url=video_url
        )
        await self.wait_for_container(container_id, timeout=120)
        return await self.publish_container(container_id)

    # ---- DM (Messaging) ----

    async def send_dm(self, recipient_id: str, message: str) -> dict:
        """Send a DM to a user (must have interacted within 24h)."""
        return await self.post(
            f"/{self.config.page_id}/messages",
            recipient=f'{{"id": "{recipient_id}"}}',
            message=f'{{"text": "{message}"}}',
            messaging_type="RESPONSE",
        )

    # ---- Comments ----

    async def get_media_comments(self, media_id: str) -> list[dict]:
        """Get comments on a media object."""
        data = await self.get(
            f"/{media_id}/comments",
            fields="id,text,from,timestamp",
        )
        return data.get("data", [])

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Reply to a comment."""
        return await self.post(
            f"/{comment_id}/replies",
            message=message,
        )

    # ---- Insights ----

    async def get_media_insights(self, media_id: str) -> dict:
        """Get insights for a published media object."""
        data = await self.get(
            f"/{media_id}/insights",
            metric="impressions,reach,engagement,saved,shares",
        )
        metrics = {}
        for item in data.get("data", []):
            metrics[item["name"]] = item["values"][0]["value"]
        return metrics

    async def get_account_insights(
        self, period: str = "day", since: int | None = None, until: int | None = None
    ) -> dict:
        """Get account-level insights."""
        params: dict[str, Any] = {
            "metric": "impressions,reach,follower_count,profile_views",
            "period": period,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await self.get(
            f"/{self.config.ig_user_id}/insights", **params
        )

    async def get_recent_media(self, limit: int = 25) -> list[dict]:
        """Get recent media posts."""
        data = await self.get(
            f"/{self.config.ig_user_id}/media",
            fields="id,caption,media_type,timestamp,like_count,comments_count,permalink",
            limit=limit,
        )
        return data.get("data", [])
