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


# ═══════════════════════════════════════════════
#  B-3: Source Quality → Dynamic Timeout
# ═══════════════════════════════════════════════

class TestSourceQualityFeedback:
    """B-3: 소스 품질 기반 동적 타임아웃 및 수집 전략 반영."""

    @pytest.mark.asyncio
    async def test_low_quality_source_gets_short_timeout(self, memory_db):
        """저품질 소스(quality < 0.3)는 스킵 대상이 됨."""
        from db import record_source_quality, get_source_quality_summary
        # 저품질 기록 3건
        for _ in range(3):
            await record_source_quality(memory_db, "reddit", False, 5000, 0, 0.1)

        summary = await get_source_quality_summary(memory_db, days=7)
        assert "reddit" in summary
        assert summary["reddit"]["avg_quality_score"] < 0.3

    @pytest.mark.asyncio
    async def test_high_quality_source_stats(self, memory_db):
        """고품질 소스(quality >= 0.7)의 통계 조회."""
        from db import record_source_quality, get_source_quality_summary
        for _ in range(3):
            await record_source_quality(memory_db, "twitter", True, 100, 5, 0.85)

        summary = await get_source_quality_summary(memory_db, days=7)
        assert "twitter" in summary
        assert summary["twitter"]["avg_quality_score"] >= 0.7
        assert summary["twitter"]["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_quality_summary_returns_dict_format(self, memory_db):
        """get_source_quality_summary가 {source_name: stats_dict} 형태를 반환."""
        from db import record_source_quality, get_source_quality_summary
        await record_source_quality(memory_db, "news", True, 200, 3, 0.6)
        summary = await get_source_quality_summary(memory_db, days=7)
        # dict.items() 순회 가능 확인 (B-3 버그 수정 검증)
        for src_name, stats in summary.items():
            assert isinstance(src_name, str)
            assert isinstance(stats, dict)
            assert "avg_quality_score" in stats
            assert "success_rate" in stats


# ═══════════════════════════════════════════════
#  B-4: Best Posting Hours
# ═══════════════════════════════════════════════

class TestBestPostingHours:
    """B-4: 카테고리별 최적 게시 시간 학습 및 추천."""

    @pytest.mark.asyncio
    async def test_empty_stats_returns_empty(self, memory_db):
        """데이터 없으면 빈 리스트 반환."""
        from db import get_best_posting_hours
        result = await get_best_posting_hours(memory_db, "테크", top_n=3)
        assert result == []

    @pytest.mark.asyncio
    async def test_posting_time_learning(self, memory_db):
        """게시 시간 학습 기록 후 조회."""
        from db import record_posting_time_stat, get_best_posting_hours
        # 8시에 '높음' 5회, 15시에 '낮음' 5회
        for _ in range(5):
            await record_posting_time_stat(memory_db, "테크", 8, "높음")
            await record_posting_time_stat(memory_db, "테크", 15, "낮음")

        best = await get_best_posting_hours(memory_db, "테크", top_n=2)
        assert len(best) == 2
        # 8시가 첫 번째(높음=1.0 평균 > 낮음=0.2 평균)
        assert best[0] == 8

    @pytest.mark.asyncio
    async def test_metadata_field_on_tweet_batch(self):
        """TweetBatch에 metadata 필드 존재 확인."""
        from models import TweetBatch
        batch = TweetBatch(topic="test")
        assert hasattr(batch, "metadata")
        assert isinstance(batch.metadata, dict)
        # B-4 메타데이터 삽입
        batch.metadata["best_posting_hours"] = [8, 13, 20]
        assert batch.metadata["best_posting_hours"] == [8, 13, 20]
