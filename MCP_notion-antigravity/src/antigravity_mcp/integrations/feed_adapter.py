from __future__ import annotations

from typing import Any

import feedparser
import httpx

from antigravity_mcp.config import get_settings


class FeedAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_entries(self, url: str, *, timeout_sec: int | None = None) -> list[Any]:
        timeout = timeout_sec or self.settings.pipeline_http_timeout_sec
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "AntigravityContentEngine/0.1 (+https://notion.so)"},
            )
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        return list(parsed.entries)
