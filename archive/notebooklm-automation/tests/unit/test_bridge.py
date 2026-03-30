"""Unit tests for bridge module — all using mocked NotebookLM client."""

from __future__ import annotations

from notebooklm_automation.bridge import (
    _extract_urls_from_context,
    content_factory,
    trend_to_notebook,
)


class TestTrendToNotebook:
    async def test_creates_notebook_and_adds_sources(self, patch_notebooklm):
        client = patch_notebooklm
        result = await trend_to_notebook(
            keyword="AI 에이전트",
            urls=["https://example.com/1", "https://example.com/2"],
            category="테크",
        )

        assert result["notebook_id"] == "test-notebook-id-1234"
        assert len(result["source_ids"]) == 2
        assert result["summary"] == "테스트 AI 요약 결과입니다."
        client.notebooks.create.assert_awaited_once()
        assert client.sources.add_url.await_count == 2

    async def test_handles_source_add_failure(self, patch_notebooklm):
        client = patch_notebooklm
        client.sources.add_url.side_effect = Exception("network error")

        result = await trend_to_notebook(keyword="test", urls=["https://fail.com"])
        assert result["notebook_id"] == "test-notebook-id-1234"
        assert result["source_ids"] == []

    async def test_skips_summary_when_no_sources(self, patch_notebooklm):
        client = patch_notebooklm
        client.sources.add_url.side_effect = Exception("all fail")

        result = await trend_to_notebook(keyword="test", urls=["https://fail.com"])
        assert result["summary"] == ""
        client.chat.ask.assert_not_awaited()


class TestContentFactory:
    async def test_produces_all_outputs(self, patch_notebooklm):
        client = patch_notebooklm
        result = await content_factory(
            keyword="CRISPR",
            urls=["https://paper.com/1"],
            category="바이오",
        )

        assert result["notebook_id"] == "test-notebook-id-1234"
        assert result["source_count"] == 1
        assert result["summary"] != ""
        assert result["tweet_draft"] != ""
        # chat.ask should be called for both insight and tweet
        assert client.chat.ask.await_count == 2

    async def test_continues_on_infographic_failure(self, patch_notebooklm):
        client = patch_notebooklm
        client.artifacts.generate_infographic.side_effect = Exception("infographic fail")

        result = await content_factory(keyword="test", urls=["https://x.com"])
        assert result["infographic_id"] == ""
        assert result["notebook_id"] != ""


class TestExtractUrlsFromContext:
    def test_extracts_from_sources_list(self):
        ctx = type("Ctx", (), {"sources": ["https://a.com", "https://b.com"], "news_insight": ""})()
        urls = _extract_urls_from_context(ctx)
        assert urls == ["https://a.com", "https://b.com"]

    def test_extracts_from_dict_sources(self):
        ctx = type("Ctx", (), {"sources": [{"url": "https://c.com"}], "news_insight": ""})()
        urls = _extract_urls_from_context(ctx)
        assert urls == ["https://c.com"]

    def test_extracts_from_news_insight(self):
        ctx = type("Ctx", (), {"sources": [], "news_insight": "Check https://news.com/article"})()
        urls = _extract_urls_from_context(ctx)
        assert urls == ["https://news.com/article"]

    def test_deduplicates(self):
        ctx = type("Ctx", (), {"sources": ["https://a.com", "https://a.com"], "news_insight": "https://a.com"})()
        urls = _extract_urls_from_context(ctx)
        assert urls == ["https://a.com"]
