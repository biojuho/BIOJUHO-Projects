# -*- coding: utf-8 -*-
"""
v15.0 Phase C Tests
  C-1: Google Trends related query collection
  C-2: Source quality API (source_quality)
  C-3: CI/CD config basic validation
"""
import pytest

from models import MultiSourceContext, RawTrend, TrendSource


# ═══════════════════════════════════════════════
#  C-1: Google Trends Related Queries
# ═══════════════════════════════════════════════

@pytest.mark.skip(reason="Phase C not yet implemented: _async_fetch_google_trends_related")
class TestGoogleTrendsRelated:
    """Google Trends related query extraction logic test."""

    @pytest.mark.asyncio
    async def test_related_extracts_from_google_trends_source(self):
        """Google Trends news_headlines are converted to related queries."""
        from scraper import _async_fetch_google_trends_related
        import httpx

        trends = [
            RawTrend(
                name="AI기술",
                source=TrendSource.GOOGLE_TRENDS,
                extra={"news_headlines": ["ChatGPT 업데이트", "AI 규제 논의"]},
            ),
            RawTrend(
                name="반도체",
                source=TrendSource.GETDAYTRENDS,
            ),
        ]

        async with httpx.AsyncClient() as session:
            result = await _async_fetch_google_trends_related(
                session, trends, "korea"
            )

        assert "AI기술" in result
        assert len(result["AI기술"]) == 2
        assert "ChatGPT 업데이트" in result["AI기술"]

    @pytest.mark.asyncio
    async def test_empty_trends_returns_empty(self):
        """Empty trend list returns empty dict."""
        from scraper import _async_fetch_google_trends_related
        import httpx

        async with httpx.AsyncClient() as session:
            result = await _async_fetch_google_trends_related(
                session, [], "korea"
            )

        assert result == {}


# ═══════════════════════════════════════════════
#  C-2: Source Quality API
# ═══════════════════════════════════════════════

class TestSourceQualityDB:
    """Source quality metrics DB function tests."""

    @pytest.mark.asyncio
    async def test_empty_source_quality(self, memory_db):
        from db import get_source_quality_summary
        result = await get_source_quality_summary(memory_db, days=7)
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_source_record(self, memory_db):
        from db import get_source_quality_summary, record_source_quality
        await record_source_quality(
            memory_db, source="google_trends",
            success=True, latency_ms=150.0, item_count=20, quality_score=0.8,
        )
        result = await get_source_quality_summary(memory_db, days=7)
        assert "google_trends" in result
        assert result["google_trends"]["total_calls"] == 1
        assert result["google_trends"]["avg_quality_score"] == 0.8

    @pytest.mark.asyncio
    async def test_multiple_sources(self, memory_db):
        from db import get_source_quality_summary, record_source_quality
        await record_source_quality(memory_db, "twitter", True, 200, 5, 0.6)
        await record_source_quality(memory_db, "twitter", True, 100, 3, 0.4)
        await record_source_quality(memory_db, "reddit", False, 5000, 0, 0.0)
        result = await get_source_quality_summary(memory_db, days=7)
        assert "twitter" in result
        assert "reddit" in result
        assert result["twitter"]["total_calls"] == 2
        assert result["reddit"]["success_rate"] == 0.0


# ═══════════════════════════════════════════════
#  C-3: CI/CD Config Validation
# ═══════════════════════════════════════════════

@pytest.mark.skip(reason="Phase C not yet implemented: get_qa_summary, get_content_hashes, select_persona")
class TestPhaseCSmokeConfig:
    """Phase C config basic validation + env variable loading."""

    def test_google_suggest_function_exists(self):
        """Google Suggest function exists in scraper module."""
        from scraper import _async_fetch_google_suggest
        assert callable(_async_fetch_google_suggest)

    def test_google_trends_related_function_exists(self):
        """Google Trends related query function exists in scraper module."""
        from scraper import _async_fetch_google_trends_related
        assert callable(_async_fetch_google_trends_related)

    def test_qa_summary_function_exists(self):
        """QA metrics function exists in db module."""
        from db import get_qa_summary
        assert callable(get_qa_summary)

    def test_source_quality_summary_exists(self):
        """Source quality metrics function exists in db module."""
        from db import get_source_quality_summary
        assert callable(get_source_quality_summary)

    def test_content_hashes_function_exists(self):
        """Content hash function exists in db module."""
        from db import get_content_hashes
        assert callable(get_content_hashes)

    def test_select_persona_function_exists(self):
        """Persona selection function exists in generator module."""
        from generator import select_persona
        assert callable(select_persona)
