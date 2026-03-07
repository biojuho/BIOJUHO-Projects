from __future__ import annotations

import logging
from typing import Any

import feedparser
import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from antigravity_mcp.config import get_settings

logger = logging.getLogger(__name__)


def _build_retry_decorator(max_retries: int) -> Any:
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


class FeedAdapter:
    def __init__(self, *, state_store: Any | None = None) -> None:
        self.settings = get_settings()
        self._state_store = state_store  # optional: PipelineStateStore for ETag caching

    async def fetch_entries(self, url: str, *, timeout_sec: int | None = None) -> list[Any]:
        timeout = timeout_sec or self.settings.pipeline_http_timeout_sec
        max_retries = self.settings.pipeline_max_retries

        headers: dict[str, str] = {
            "User-Agent": "AntigravityContentEngine/0.1 (+https://notion.so)",
        }

        # Send conditional request headers if ETag/Last-Modified cached
        if self._state_store:
            cached_etag, cached_lm = self._state_store.get_feed_etag(url)
            if cached_etag:
                headers["If-None-Match"] = cached_etag
            if cached_lm:
                headers["If-Modified-Since"] = cached_lm

        response = await self._fetch_with_retry(url, headers=headers, timeout=timeout, max_retries=max_retries)
        if response is None:
            return []

        # Cache the new ETag/Last-Modified
        if self._state_store:
            new_etag = response.headers.get("ETag")
            new_lm = response.headers.get("Last-Modified")
            if new_etag or new_lm:
                self._state_store.put_feed_etag(url, new_etag, new_lm)

        parsed = feedparser.parse(response.text)
        return list(parsed.entries)

    async def _fetch_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
        max_retries: int,
    ) -> httpx.Response | None:
        """Fetch URL with exponential backoff retry. Returns None on 304, raises on persistent failure."""

        @retry(
            reraise=True,
            stop=stop_after_attempt(max(1, max_retries)),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        async def _do_fetch() -> httpx.Response | None:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 304:
                    logger.debug("Feed not modified: %s", url)
                    return None
                resp.raise_for_status()
                return resp

        return await _do_fetch()
