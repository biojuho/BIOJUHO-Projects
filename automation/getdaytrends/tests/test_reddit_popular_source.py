"""Tests for the Reddit /r/popular primary trend source."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from collectors.sources import _async_fetch_reddit_popular  # noqa: E402
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
        self.last_url = ""

    async def get(self, url, headers=None, timeout=None) -> _FakeResponse:
        self.last_url = url
        return _FakeResponse(self.payload)


def _post(
    title: str,
    *,
    ups: int = 100,
    comments: int = 10,
    subreddit: str = "r/news",
    permalink: str = "/r/news/comments/x",
    over_18: bool = False,
    stickied: bool = False,
) -> dict:
    return {
        "data": {
            "title": title,
            "ups": ups,
            "num_comments": comments,
            "subreddit_name_prefixed": subreddit,
            "permalink": permalink,
            "over_18": over_18,
            "stickied": stickied,
        }
    }


@pytest.mark.asyncio
async def test_reddit_popular_parses_children() -> None:
    payload = {
        "data": {
            "children": [
                _post("Major AI breakthrough announced", ups=15000, comments=420),
                _post("xx", ups=10),  # too short, filtered
                _post("NSFW content", over_18=True),  # filtered
                _post("Pinned post", stickied=True),  # filtered
                _post("Second story worth surfacing", ups=8000, comments=200),
            ]
        }
    }
    session = _FakeSession(payload)
    trends = await _async_fetch_reddit_popular(session, limit=10)  # type: ignore[arg-type]

    assert len(trends) == 2
    assert all(t.source == TrendSource.REDDIT for t in trends)
    assert trends[0].name == "Major AI breakthrough announced"
    # ups + comments*5 weighting
    assert trends[0].volume_numeric == 15000 + 420 * 5
    assert trends[0].extra["subreddit"] == "r/news"
    assert trends[0].link.startswith("https://www.reddit.com/r/news/comments/")


@pytest.mark.asyncio
async def test_reddit_popular_handles_empty() -> None:
    session = _FakeSession({"data": {"children": []}})
    trends = await _async_fetch_reddit_popular(session, limit=5)  # type: ignore[arg-type]
    assert trends == []


@pytest.mark.asyncio
async def test_reddit_popular_handles_missing_data_envelope() -> None:
    session = _FakeSession({})
    trends = await _async_fetch_reddit_popular(session, limit=5)  # type: ignore[arg-type]
    assert trends == []


@pytest.mark.asyncio
async def test_reddit_popular_handles_http_error() -> None:
    import httpx

    class _BoomSession:
        async def get(self, url, headers=None, timeout=None):
            raise httpx.RequestError("boom")  # type: ignore[arg-type]

    trends = await _async_fetch_reddit_popular(_BoomSession(), limit=5)  # type: ignore[arg-type]
    assert trends == []


@pytest.mark.asyncio
async def test_reddit_popular_url_includes_limit() -> None:
    session = _FakeSession({"data": {"children": []}})
    await _async_fetch_reddit_popular(session, limit=37)  # type: ignore[arg-type]
    assert "limit=37" in session.last_url
