"""Unit tests for signal_collector — Google Trends parser + GetDayTrends connector."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_mcp.integrations.signal_collector import (
    GetDayTrendsConnector,
    GoogleTrendsCollector,
    RedditRisingCollector,
    MultiSourceCollector,
    TrendSignal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_GOOGLE_TRENDS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ht="https://trends.google.co.kr/trending/rss">
<channel>
  <title>Daily Search Trends</title>
  <item>
    <title>비트코인</title>
    <ht:approx_traffic>500,000+</ht:approx_traffic>
    <pubDate>Thu, 03 Apr 2026 12:00:00 +0900</pubDate>
  </item>
  <item>
    <title>삼성전자</title>
    <ht:approx_traffic>200,000+</ht:approx_traffic>
    <pubDate>Thu, 03 Apr 2026 11:00:00 +0900</pubDate>
  </item>
  <item>
    <title>ChatGPT 5</title>
    <ht:approx_traffic>100,000+</ht:approx_traffic>
    <pubDate>Thu, 03 Apr 2026 10:00:00 +0900</pubDate>
  </item>
  <item>
    <title>날씨</title>
    <ht:approx_traffic>50,000+</ht:approx_traffic>
    <pubDate>Thu, 03 Apr 2026 09:00:00 +0900</pubDate>
  </item>
</channel>
</rss>"""


@pytest.fixture
def gdt_db(tmp_path: Path) -> Path:
    """Create a temporary GetDayTrends SQLite database with sample data."""
    db_path = tmp_path / "getdaytrends.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            rank INTEGER,
            volume_raw TEXT DEFAULT 'N/A',
            volume_numeric INTEGER DEFAULT 0,
            viral_potential INTEGER DEFAULT 0,
            trend_acceleration TEXT DEFAULT '+0%',
            cross_source_confidence INTEGER DEFAULT 0,
            scored_at TEXT NOT NULL,
            sentiment TEXT DEFAULT 'neutral'
        )
    """)
    now = datetime.now(UTC).isoformat()
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    old = (datetime.now(UTC) - timedelta(hours=12)).isoformat()

    conn.executemany(
        """INSERT INTO trends (run_id, keyword, rank, viral_potential,
           cross_source_confidence, trend_acceleration, scored_at, sentiment, volume_numeric)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, "AI 반도체", 1, 85, 3, "+250%", recent, "positive", 500000),
            (1, "비트코인", 2, 70, 2, "+150%", recent, "neutral", 300000),
            (1, "환율 폭등", 3, 60, 1, "+50%", recent, "negative", 100000),
            (1, "오래된 트렌드", 4, 40, 0, "+10%", old, "neutral", 50000),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Google Trends Collector Tests
# ---------------------------------------------------------------------------


class TestGoogleTrendsCollector:
    def test_parse_rss_basic(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss(SAMPLE_GOOGLE_TRENDS_RSS)  # noqa: SLF001
        assert len(signals) == 4
        assert signals[0].keyword == "비트코인"
        assert signals[0].source == "google_trends"
        assert signals[0].score > 0

    def test_parse_rss_respects_limit(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss(SAMPLE_GOOGLE_TRENDS_RSS, limit=2)  # noqa: SLF001
        assert len(signals) == 2

    def test_parse_rss_score_ranking(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss(SAMPLE_GOOGLE_TRENDS_RSS)  # noqa: SLF001
        # Rank 1 should have >= score than rank 2 (both may cap at 1.0 with volume boost)
        assert signals[0].score >= signals[1].score
        # Lower ranks should have strictly lower scores
        assert signals[1].score >= signals[2].score
        assert signals[2].score >= signals[3].score

    def test_parse_volume(self) -> None:
        assert GoogleTrendsCollector._parse_volume("500,000+") == 500000
        assert GoogleTrendsCollector._parse_volume("10K+") == 10000
        assert GoogleTrendsCollector._parse_volume("1M+") == 1000000
        assert GoogleTrendsCollector._parse_volume("") == 0
        assert GoogleTrendsCollector._parse_volume("invalid") == 0

    def test_category_hint(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss(SAMPLE_GOOGLE_TRENDS_RSS)  # noqa: SLF001
        # 비트코인 → Crypto
        assert signals[0].category_hint == "Crypto"
        # 삼성전자 → Tech
        assert signals[1].category_hint == "Tech"
        # ChatGPT → Tech
        assert signals[2].category_hint == "Tech"
        # 날씨 → no category
        assert signals[3].category_hint == ""

    def test_parse_rss_empty(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss("<rss><channel></channel></rss>")  # noqa: SLF001
        assert signals == []

    def test_parse_rss_invalid_xml(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss("not xml at all")  # noqa: SLF001
        assert signals == []

    def test_volume_boosts_score(self) -> None:
        collector = GoogleTrendsCollector()
        signals = collector._parse_rss(SAMPLE_GOOGLE_TRENDS_RSS)  # noqa: SLF001
        # 비트코인 (500K+, rank 1) should be boosted above raw rank score
        assert signals[0].score >= 1.0  # rank 1 + volume 500K → capped at 1.0

    @pytest.mark.asyncio
    async def test_fetch_trending_handles_error(self) -> None:
        collector = GoogleTrendsCollector()
        with patch("antigravity_mcp.integrations.signal_collector.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Network error")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance
            result = await collector.fetch_trending()
            assert result == []


# ---------------------------------------------------------------------------
# GetDayTrends Connector Tests
# ---------------------------------------------------------------------------


class TestGetDayTrendsConnector:
    def test_is_available_with_valid_path(self, gdt_db: Path) -> None:
        connector = GetDayTrendsConnector(db_path=str(gdt_db))
        assert connector.is_available

    def test_is_available_with_missing_path(self) -> None:
        connector = GetDayTrendsConnector(db_path="/nonexistent/path.db")
        assert not connector.is_available

    @pytest.mark.asyncio
    async def test_fetch_trending_returns_recent(self, gdt_db: Path) -> None:
        connector = GetDayTrendsConnector(db_path=str(gdt_db))
        signals = await connector.fetch_trending(limit=10)
        # Should include only trends from last 6 hours (3 recent, 1 old)
        assert len(signals) == 3
        # Sorted by viral_potential desc
        assert signals[0].keyword == "AI 반도체"
        assert signals[0].source == "getdaytrends"

    @pytest.mark.asyncio
    async def test_fetch_trending_score_normalisation(self, gdt_db: Path) -> None:
        connector = GetDayTrendsConnector(db_path=str(gdt_db))
        signals = await connector.fetch_trending()
        # AI 반도체: viral=85 → 0.85 * 1.3 (confidence=3) = 1.0 (capped)
        assert signals[0].score >= 0.85
        assert signals[0].score <= 1.0

    @pytest.mark.asyncio
    async def test_fetch_trending_respects_limit(self, gdt_db: Path) -> None:
        connector = GetDayTrendsConnector(db_path=str(gdt_db))
        signals = await connector.fetch_trending(limit=1)
        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_fetch_trending_unavailable_returns_empty(self) -> None:
        connector = GetDayTrendsConnector(db_path="/nonexistent/path.db")
        signals = await connector.fetch_trending()
        assert signals == []

    def test_parse_acceleration(self) -> None:
        assert GetDayTrendsConnector._parse_acceleration("+250%") == 0.5
        assert GetDayTrendsConnector._parse_acceleration("+500%") == 1.0
        assert GetDayTrendsConnector._parse_acceleration("+0%") == 0.0
        assert GetDayTrendsConnector._parse_acceleration("invalid") == 0.0

    @pytest.mark.asyncio
    async def test_raw_data_contains_metadata(self, gdt_db: Path) -> None:
        connector = GetDayTrendsConnector(db_path=str(gdt_db))
        signals = await connector.fetch_trending()
        assert "viral_potential" in signals[0].raw_data
        assert "sentiment" in signals[0].raw_data
        assert "cross_source_confidence" in signals[0].raw_data


# ---------------------------------------------------------------------------
# Reddit Rising Collector Tests
# ---------------------------------------------------------------------------


class TestRedditRisingCollector:
    def test_parse_reddit_json_basic(self) -> None:
        collector = RedditRisingCollector()
        sample_data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "A major scientific breakthrough discovery today",
                            "ups": 1500,
                            "upvote_ratio": 0.98,
                            "num_comments": 250,
                            "url": "https://example.com/breakthrough",
                        }
                    },
                    {
                        "data": {
                            "title": "Some random minor post",
                            "ups": 100,
                            "upvote_ratio": 0.85,
                            "num_comments": 5,
                        }
                    }
                ]
            }
        }
        signals = collector._parse_reddit_json("worldnews", sample_data, limit=5)
        assert len(signals) == 2
        # Title should be used as keyword
        assert signals[0].keyword == "A major scientific breakthrough discovery today"
        assert signals[0].source == "reddit"
        assert signals[0].category_hint == "WorldNews"
        
        # Check scores - first post has high upvotes and ratio, so high score
        assert signals[0].score > signals[1].score
        assert signals[0].velocity > signals[1].velocity
        
        # Validate metadata extraction
        assert signals[0].raw_data["upvotes"] == 1500
        assert signals[0].raw_data["upvote_ratio"] == 0.98
        assert signals[0].raw_data["comments"] == 250
        assert signals[0].raw_data["subreddit"] == "worldnews"

    def test_parse_reddit_json_empty_or_invalid(self) -> None:
        collector = RedditRisingCollector()
        assert collector._parse_reddit_json("popular", {}) == []
        assert collector._parse_reddit_json("popular", {"data": {}}) == []
        assert collector._parse_reddit_json("popular", {"data": {"children": []}}) == []
        
        # Missing title or empty title should be skipped
        invalid_data = {
            "data": {
                "children": [{"data": {"ups": 10}}, {"data": {"title": "  "}}]
            }
        }
        assert collector._parse_reddit_json("popular", invalid_data) == []

    @pytest.mark.asyncio
    async def test_fetch_trending_basic(self) -> None:
        collector = RedditRisingCollector(subreddits=["popular", "worldnews"])
        # Mock specific responses based on subreddit
        def mock_get(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            if "popular" in url:
                mock_resp.json.return_value = {
                    "data": {"children": [{"data": {"title": "Viral Video", "ups": 5000}}]}
                }
            else:
                mock_resp.json.return_value = {
                    "data": {"children": [{"data": {"title": "Global News", "ups": 1000}}]}
                }
            return mock_resp

        with patch("antigravity_mcp.integrations.signal_collector.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = mock_get
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance
            
            signals = await collector.fetch_trending(limit=10)
            assert len(signals) == 2
            keywords = {s.keyword for s in signals}
            assert "Viral Video" in keywords
            assert "Global News" in keywords

    @pytest.mark.asyncio
    async def test_fetch_trending_deduplication(self) -> None:
        collector = RedditRisingCollector(subreddits=["popular", "news"])
        # Mock the same title appearing in both
        with patch("antigravity_mcp.integrations.signal_collector.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "data": {"children": [{"data": {"title": "Overlapping News", "ups": 2000}}]}
            }
            mock_instance.get.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance
            
            signals = await collector.fetch_trending()
            # Should be deduplicated to 1
            assert len(signals) == 1
            assert signals[0].keyword == "Overlapping News"

    @pytest.mark.asyncio
    async def test_fetch_trending_handles_error(self) -> None:
        collector = RedditRisingCollector()
        with patch("antigravity_mcp.integrations.signal_collector.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Reddit blocked")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance
            
            result = await collector.fetch_trending()
            assert result == []


# ---------------------------------------------------------------------------
# MultiSourceCollector Tests
# ---------------------------------------------------------------------------


class TestMultiSourceCollector:
    @pytest.mark.asyncio
    async def test_collect_all_merges_sources(self, gdt_db: Path) -> None:
        google = GoogleTrendsCollector()
        gdt = GetDayTrendsConnector(db_path=str(gdt_db))

        # Mock Google to return parsed results
        with patch.object(google, "fetch_trending", return_value=[
            TrendSignal(keyword="AI 반도체", score=0.9, source="google_trends"),
        ]):
            collector = MultiSourceCollector(sources=[google, gdt])
            all_signals = await collector.collect_all()

        # Should have signals from both sources
        sources = {s.source for s in all_signals}
        assert "google_trends" in sources
        assert "getdaytrends" in sources

    @pytest.mark.asyncio
    async def test_collect_all_handles_source_failure(self) -> None:
        failing_source = MagicMock()
        failing_source.source_name = "broken"
        failing_source.fetch_trending = AsyncMock(side_effect=Exception("fail"))

        collector = MultiSourceCollector(sources=[failing_source])
        result = await collector.collect_all()
        assert result == []  # Graceful degradation

    @pytest.mark.asyncio
    async def test_source_names(self, gdt_db: Path) -> None:
        gdt = GetDayTrendsConnector(db_path=str(gdt_db))
        collector = MultiSourceCollector(sources=[gdt])
        assert "getdaytrends" in collector.source_names


# ---------------------------------------------------------------------------
# TrendSignal Model Tests
# ---------------------------------------------------------------------------


class TestTrendSignal:
    def test_default_first_seen(self) -> None:
        signal = TrendSignal(keyword="test", score=0.5, source="test_source")
        assert signal.first_seen_at  # Should auto-fill

    def test_explicit_first_seen(self) -> None:
        signal = TrendSignal(
            keyword="test", score=0.5, source="test_source",
            first_seen_at="2026-01-01T00:00:00Z",
        )
        assert signal.first_seen_at == "2026-01-01T00:00:00Z"
