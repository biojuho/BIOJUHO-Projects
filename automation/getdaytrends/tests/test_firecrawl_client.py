"""Tests for the Firecrawl API client response handling."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from firecrawl_client import FirecrawlClient  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    is_closed = False

    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.request_json = {}

    async def post(self, path: str, json: dict) -> _FakeResponse:
        self.request_json = json
        return self.response


@pytest.mark.asyncio
async def test_scrape_url_returns_empty_without_api_key() -> None:
    client = FirecrawlClient(api_key="")

    result = await client.scrape_url("https://example.test")

    assert result == {"title": "", "content": "", "published_date": ""}


@pytest.mark.asyncio
async def test_scrape_url_parses_success_and_truncates_content() -> None:
    markdown = "x" * 3100
    fake = _FakeClient(
        _FakeResponse(
            {
                "success": True,
                "data": {
                    "markdown": markdown,
                    "metadata": {"ogTitle": "Open graph title", "articlePublishedTime": "2026-05-20"},
                },
            }
        )
    )
    client = FirecrawlClient(api_key="key")
    client._client = fake  # type: ignore[assignment]

    result = await client.scrape_url("https://example.test")

    assert fake.request_json["onlyMainContent"] is True
    assert result["title"] == "Open graph title"
    assert result["published_date"] == "2026-05-20"
    assert result["content"].endswith("\n...(truncated)")


@pytest.mark.asyncio
async def test_scrape_url_returns_empty_on_quota_status() -> None:
    client = FirecrawlClient(api_key="key")
    client._client = _FakeClient(_FakeResponse({}, status_code=402))  # type: ignore[assignment]

    result = await client.scrape_url("https://example.test")

    assert result == {"title": "", "content": "", "published_date": ""}


@pytest.mark.asyncio
async def test_enrich_trend_context_formats_successful_scrapes() -> None:
    class _Client(FirecrawlClient):
        async def scrape_url(self, url: str) -> dict:
            if url.endswith("empty"):
                return {"title": "", "content": "", "published_date": ""}
            return {"title": "Headline", "content": " Body ", "published_date": "2026-05-20"}

    client = _Client(api_key="key")

    result = await client.enrich_trend_context("AI", ["https://example.test/1", "https://example.test/empty"])

    assert result.startswith("[기사 본문 요약]")
    assert "--- 기사 1 (2026-05-20) ---" in result
    assert "제목: Headline" in result
    assert "본문:\nBody" in result
