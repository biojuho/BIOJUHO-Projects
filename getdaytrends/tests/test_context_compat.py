from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock

import httpx
import pytest

import collectors.context as context


@pytest.mark.asyncio
async def test_twikit_unavailable_falls_back_to_jina(monkeypatch) -> None:
    fake_x_client = types.SimpleNamespace(
        is_available=lambda: False,
        search_tweets_formatted=AsyncMock(return_value=""),
    )
    fallback = AsyncMock(return_value="from-jina")

    monkeypatch.setitem(sys.modules, "x_client", fake_x_client)
    monkeypatch.setattr(context, "_async_fetch_x_via_jina", fallback)

    async with httpx.AsyncClient() as session:
        result = await context._async_fetch_x_via_twikit_or_jina(session, "python")

    assert result == "from-jina"
    fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_single_source_passes_timeout_override(monkeypatch) -> None:
    captured: dict[str, httpx.Timeout | float | None] = {}

    async def fake_fetch(
        session: httpx.AsyncClient,
        keyword: str,
        bearer_token: str = "",
        timeout: httpx.Timeout | float | None = None,
    ) -> str:
        captured["timeout"] = timeout
        return "ok"

    monkeypatch.setattr(context, "_async_fetch_twitter_trends", fake_fetch)

    async with httpx.AsyncClient() as session:
        result = await context._async_fetch_single_source(
            session,
            "python",
            "twitter",
            timeout_override=2.5,
        )

    assert result == ("python", "twitter", "ok")
    assert captured["timeout"] == 2.5
