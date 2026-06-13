"""Tests for Crawl4AI adapter context formatting."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

import crawl4ai_adapter  # noqa: E402


@pytest.mark.asyncio
async def test_enrich_trend_context_formats_successful_articles(monkeypatch) -> None:
    async def fake_scrape(url: str) -> dict:
        if url.endswith("skip"):
            return {"title": "", "content": "", "published_date": ""}
        return {"title": "Headline", "content": " Body ", "published_date": "2026-05-20"}

    monkeypatch.setattr(crawl4ai_adapter, "is_available", lambda: True)
    monkeypatch.setattr(crawl4ai_adapter, "scrape_url", fake_scrape)

    result = await crawl4ai_adapter.enrich_trend_context("AI", ["https://a.test/1", "https://a.test/skip"])

    assert result.startswith("[기사 본문 요약]")
    assert "--- 기사 1 (2026-05-20) ---" in result
    assert "제목: Headline" in result
    assert "본문:\nBody" in result


@pytest.mark.asyncio
async def test_enrich_trend_context_returns_empty_when_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(crawl4ai_adapter, "is_available", lambda: False)

    result = await crawl4ai_adapter.enrich_trend_context("AI", ["https://a.test/1"])

    assert result == ""
