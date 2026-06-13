from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime

import pytest


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body


class _FakeSession:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        return _FakeResponse(self.body)


def _rss(items: list[tuple[str, str]]) -> str:
    rendered_items = (
        f"<item><title>{title}</title><pubDate>{date}</pubDate></item>"
        for title, date in items
    )
    return (
        "<rss><channel>"
        + "".join(rendered_items)
        + "</channel></rss>"
    )


@pytest.mark.asyncio
async def test_google_news_collector_dedupes_titles_and_formats_fresh_headlines():
    from collectors.google_news import _async_fetch_google_news_trends

    pub_date = format_datetime(datetime.now(UTC))
    session = _FakeSession(
        _rss(
            [
                ("AI regulation accelerates", pub_date),
                ("AI regulation accelerates", pub_date),
            ]
        )
    )

    result = await _async_fetch_google_news_trends(session, "AI regulation")

    assert result.count("AI regulation accelerates") == 1
    assert "news.google.com/rss/search" in session.urls[0]
    assert "AI%20regulation" in session.urls[0]


@pytest.mark.asyncio
async def test_google_news_collector_filters_stale_headlines():
    from collectors.google_news import _async_fetch_google_news_trends

    old_date = "Mon, 01 Jan 2001 00:00:00 GMT"
    session = _FakeSession(_rss([("stale headline", old_date)]))

    result = await _async_fetch_google_news_trends(session, "AI regulation")

    assert "stale headline" not in result
