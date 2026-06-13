"""Tests for the X/Twitter recent-search collector helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from collectors.twitter import _async_fetch_twitter_trends  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, headers: dict | None = None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.request_headers = {}

    async def get(self, url, headers=None, timeout=None) -> _FakeResponse:
        self.request_headers = headers or {}
        return self.response


@pytest.mark.asyncio
async def test_twitter_recent_search_sorts_and_formats_by_engagement() -> None:
    session = _FakeSession(
        _FakeResponse(
            {
                "data": [
                    {
                        "text": "lower signal",
                        "created_at": "2026-05-20T00:00:00Z",
                        "public_metrics": {"like_count": 1, "retweet_count": 1, "quote_count": 0},
                    },
                    {
                        "text": "higher\nsignal",
                        "created_at": "2026-05-20T01:30:00Z",
                        "public_metrics": {"like_count": 5, "retweet_count": 3, "quote_count": 2},
                    },
                ]
            }
        )
    )

    result = await _async_fetch_twitter_trends(session, "AI", bearer_token="token")  # type: ignore[arg-type]

    assert session.request_headers["Authorization"] == "Bearer token"
    assert result.splitlines()[0].endswith("[5L/3RT] higher signal")
    assert "[05/20 10:30]" in result.splitlines()[0]


@pytest.mark.asyncio
async def test_twitter_recent_search_handles_empty_data() -> None:
    session = _FakeSession(_FakeResponse({}))

    result = await _async_fetch_twitter_trends(session, "AI", bearer_token="token")  # type: ignore[arg-type]

    assert result == "최근 관련 트윗 없음"
