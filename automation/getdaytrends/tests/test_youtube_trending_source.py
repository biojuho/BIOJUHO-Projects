from __future__ import annotations

import pytest
from models import TrendSource


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class _FakeSession:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        return _FakeResponse(self.body)


def _youtube_feed(entries: str) -> str:
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
        f"{entries}</feed>"
    )


def _entry(title: str, link: str, view_count: str | None = None) -> str:
    stats = f'<yt:statistics viewCount="{view_count}" />' if view_count is not None else ""
    return f'<entry><title>{title}</title><link href="{link}" />{stats}</entry>'


@pytest.mark.asyncio
async def test_youtube_trending_parses_entries_and_country_url():
    from collectors.sources import _async_fetch_youtube_trending

    session = _FakeSession(
        _youtube_feed(
            _entry("AI launch demo", "https://youtube.test/watch?v=1", "123456")
            + _entry("x", "https://youtube.test/watch?v=2", "7")
        )
    )

    trends = await _async_fetch_youtube_trending(session, "united-states", limit=10)

    assert session.urls == ["https://www.youtube.com/feeds/videos.xml?gl=US&hl=ko"]
    assert len(trends) == 1
    assert trends[0].name == "AI launch demo"
    assert trends[0].source == TrendSource.YOUTUBE
    assert trends[0].volume == "123,456 views"
    assert trends[0].volume_numeric == 123456
    assert trends[0].link == "https://youtube.test/watch?v=1"
    assert trends[0].country == "united-states"


@pytest.mark.asyncio
async def test_youtube_trending_handles_invalid_view_counts_and_limits():
    from collectors.sources import _async_fetch_youtube_trending

    session = _FakeSession(
        _youtube_feed(
            _entry("First video", "https://youtube.test/watch?v=1", "not-a-number")
            + _entry("Second video", "https://youtube.test/watch?v=2", "1000")
        )
    )

    trends = await _async_fetch_youtube_trending(session, "unknown-country", limit=1)

    assert session.urls == ["https://www.youtube.com/feeds/videos.xml?gl=KR&hl=ko"]
    assert len(trends) == 1
    assert trends[0].name == "First video"
    assert trends[0].volume == "N/A"
    assert trends[0].volume_numeric == 0
