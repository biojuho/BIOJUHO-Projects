from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_GDT_ROOT = Path(__file__).resolve().parents[1]
if str(_GDT_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDT_ROOT))

import firecrawl_bridge
from firecrawl_bridge import _extract_news_urls, enrich_contexts_with_firecrawl


class FakeClient:
    available = True

    def __init__(self):
        self.closed = False
        self.calls = []

    async def enrich_trend_context(self, keyword, urls, max_articles):
        self.calls.append((keyword, urls, max_articles))
        return f"full text for {keyword}"

    async def close(self):
        self.closed = True


def test_extract_news_urls_supports_known_context_shapes():
    object_ctx = SimpleNamespace(news_items=[SimpleNamespace(url="https://a.test"), {"url": "https://b.test"}])
    news_ctx = SimpleNamespace(news=[{"url": "https://c.test"}])
    dict_ctx = {"news": [{"url": "https://d.test"}]}

    assert _extract_news_urls(object_ctx) == ["https://a.test", "https://b.test"]
    assert _extract_news_urls(news_ctx) == ["https://c.test"]
    assert _extract_news_urls(dict_ctx) == ["https://d.test"]


@pytest.mark.asyncio
async def test_enrich_contexts_with_firecrawl_updates_dict_context(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(firecrawl_bridge, "_get_backend", lambda: "firecrawl")
    monkeypatch.setattr(firecrawl_bridge, "get_firecrawl_client", lambda: fake_client)

    trend = SimpleNamespace(keyword="topic", viral_potential=90)
    contexts = {"topic": {"news": [{"url": "https://news.test/story"}]}}

    result = await enrich_contexts_with_firecrawl(
        [trend],
        contexts,
        max_articles_per_trend=2,
        min_score_for_enrichment=60,
    )

    assert result is contexts
    assert contexts["topic"]["firecrawl_context"] == "full text for topic"
    assert fake_client.calls == [("topic", ["https://news.test/story"], 2)]
    assert fake_client.closed is True
