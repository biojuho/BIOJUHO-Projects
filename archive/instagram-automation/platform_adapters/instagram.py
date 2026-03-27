"""Instagram platform adapter.

Wraps the existing MetaGraphAPI client to conform to the
PlatformAdapter interface for multi-platform support.
"""

from __future__ import annotations

import logging

from config import MetaAPIConfig
from platform_adapters import PlatformAdapter, PostContent, PublishResult
from services.meta_api import MetaAPIError, MetaGraphAPI

logger = logging.getLogger(__name__)


class InstagramAdapter(PlatformAdapter):
    """Instagram adapter using Meta Graph API."""

    platform_name = "instagram"

    def __init__(self, config: MetaAPIConfig):
        self._api = MetaGraphAPI(config)
        self._config = config

    async def authenticate(self) -> bool:
        """Check if access token and account ID are valid."""
        try:
            info = await self._api.get_account_info()
            logger.info(
                "Instagram authenticated: @%s (%s followers)",
                info.get("username", "?"),
                info.get("followers_count", "?"),
            )
            return True
        except MetaAPIError as e:
            logger.error("Instagram auth failed: %s (code=%d)", e, e.code)
            return False

    async def publish(self, content: PostContent) -> PublishResult:
        """Publish content via Meta Graph API."""
        try:
            caption = content.full_caption

            if content.post_type == "REEL" and content.video_url:
                media_id = await self._api.publish_reel(
                    content.video_url, caption
                )
            elif content.post_type == "CAROUSEL" and content.carousel_urls:
                media_id = await self._api.publish_carousel(
                    content.carousel_urls, caption
                )
            elif content.post_type == "STORY":
                media_id = await self._api.publish_story(
                    image_url=content.image_url,
                    video_url=content.video_url,
                )
            else:
                # Default: image post
                if not content.image_url:
                    return PublishResult(
                        platform=self.platform_name,
                        post_id="",
                        success=False,
                        error="No image_url for IMAGE post",
                    )
                media_id = await self._api.publish_image(
                    content.image_url, caption
                )

            url = f"https://www.instagram.com/p/{media_id}/"
            logger.info("Published to Instagram: %s", media_id)
            return PublishResult(
                platform=self.platform_name,
                post_id=media_id,
                url=url,
            )

        except MetaAPIError as e:
            logger.error("Instagram publish failed: %s", e)
            return PublishResult(
                platform=self.platform_name,
                post_id="",
                success=False,
                error=str(e),
            )

    async def get_insights(self, post_id: str) -> dict:
        """Get Instagram insights for a published post."""
        try:
            return await self._api.get_media_insights(post_id)
        except MetaAPIError as e:
            logger.warning("Insights fetch failed for %s: %s", post_id, e)
            return {"error": str(e)}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._api.close()
