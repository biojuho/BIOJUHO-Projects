"""Tests for the Hacker News supplemental trend source."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from collectors.sources import _async_fetch_hacker_news  # noqa: E402
from models import TrendSource  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def get(self, url, headers=None, timeout=None) -> _FakeResponse:
        return _FakeResponse(self.payload)


@pytest.mark.asyncio
async def test_hacker_news_parses_hits() -> None:
    payload = {
        "hits": [
            {
                "title": "Show HN: New AI tool",
                "url": "https://example.com/a",
                "points": 200,
                "num_comments": 45,
                "objectID": "1",
            },
            {
                "title": "x",  # too short, should be filtered
                "points": 10,
                "num_comments": 0,
                "objectID": "2",
            },
            {
                "story_title": "Fallback story title",
                "points": 50,
                "num_comments": 12,
                "objectID": "3",
            },
        ]
    }
    session = _FakeSession(payload)
    trends = await _async_fetch_hacker_news(session, limit=10)  # type: ignore[arg-type]

    assert len(trends) == 2  # short title filtered
    assert trends[0].source == TrendSource.HACKER_NEWS
    assert trends[0].name == "Show HN: New AI tool"
    assert trends[0].volume_numeric == 200 * 10 + 45
    assert trends[0].extra == {"points": 200, "comments": 45}
    assert trends[1].name == "Fallback story title"
    # objectID-only fallback link
    assert "news.ycombinator.com/item?id=3" in trends[1].link


@pytest.mark.asyncio
async def test_hacker_news_handles_empty_payload() -> None:
    session = _FakeSession({"hits": []})
    trends = await _async_fetch_hacker_news(session, limit=5)  # type: ignore[arg-type]
    assert trends == []


@pytest.mark.asyncio
async def test_hacker_news_handles_http_error() -> None:
    class _BoomSession:
        async def get(self, url, headers=None, timeout=None):
            import httpx

            raise httpx.RequestError("boom", request=None)  # type: ignore[arg-type]

    trends = await _async_fetch_hacker_news(_BoomSession(), limit=5)  # type: ignore[arg-type]
    assert trends == []
