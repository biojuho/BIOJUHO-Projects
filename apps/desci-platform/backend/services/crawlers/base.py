"""Base class for RFP notice crawlers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger("biolinker.crawlers")


@dataclass
class Notice:
    id: str
    title: str
    agency: str
    deadline: str
    url: str
    amount: str = ""
    description: str = ""


class BaseCrawler:
    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with retry on 429/5xx."""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, **kwargs)
                    if resp.status_code == 429:
                        await asyncio.sleep(2**attempt)
                        continue
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError(f"Failed after {self.max_retries} retries")

    async def collect(self) -> list[Notice]:
        """Override in subclass."""
        raise NotImplementedError
