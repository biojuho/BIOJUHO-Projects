"""TAP (Trend Arbitrage Publisher) 테스트 스위트."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════

def _make_trend_row(keyword: str, country: str, viral: int, hours_ago: float = 2.0):
    scored_at = (datetime.now() - timedelta(hours=hours_ago)).isoformat()
    return {
        "keyword": keyword,
        "country": country,
        "viral_potential": viral,
        "scored_at": scored_at,
    }


def _mock_conn_with_trends(trends: list[dict]):
    """DB 연결 mock: execute() → fetchall() → trends 반환."""
    cursor_mock = AsyncMock()
    cursor_mock.fetchall = AsyncMock(return_value=trends)
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=cursor_mock)
    return conn


# ══════════════════════════════════════════════════════
#  Detector Tests
# ══════════════════════════════════════════════════════

class TestKeywordSimilarity:
    """키워드 유사도 매칭 테스트."""

    def test_exact_match(self):
        from tap.detector import _is_same_topic
        assert _is_same_topic("Bitcoin", "bitcoin") is True

    def test_substring_match(self):
        from tap.detector import _is_same_topic
        assert _is_same_topic("Bitcoin ETF", "BitcoinETF") is True

    def test_bigram_similarity(self):
        from tap.detector import _is_same_topic
        assert _is_same_topic("bitcoin price", "bitcoinprice") is True

    def test_different_topics(self):
        from tap.detector import _is_same_topic
        assert _is_same_topic("Bitcoin", "Ethereum") is False

    def test_empty_keyword(self):
        from tap.detector import _is_same_topic
        assert _is_same_topic("", "Bitcoin") is False
        assert _is_same_topic("Bitcoin", "") is False


class TestTimePriorityFactor:
    """시간 우선도 계수 테스트."""

    def test_very_early(self):
        from tap.detector import _time_priority_factor
        assert _time_priority_factor(0.3) == 0.2

    def test_sweet_spot(self):
        from tap.detector import _time_priority_factor
        assert _time_priority_factor(5.0) == 1.0

    def test_declining(self):
        from tap.detector import _time_priority_factor
        factor = _time_priority_factor(10.0)
        assert 0.3 < factor < 1.0

    def test_very_late(self):
        from tap.detector import _time_priority_factor
        factor = _time_priority_factor(20.0)
        assert factor >= 0.1


class TestTrendArbitrageDetector:
    """핵심 감지기 테스트."""

    @pytest.mark.asyncio
    async def test_single_country_returns_empty(self):
        """단일 국가면 빈 결과."""
        from tap.detector import TrendArbitrageDetector
        trends = [
            _make_trend_row("AI혁명", "korea", 85, 3.0),
            _make_trend_row("반도체", "korea", 70, 2.0),
        ]
        conn = _mock_conn_with_trends(trends)
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()
        assert result == []

    @pytest.mark.asyncio
    async def test_cross_country_detects_gap(self):
        """한국에서 트렌딩이고 미국에서 미감지인 키워드 감지."""
        from tap.detector import TrendArbitrageDetector
        trends = [
            _make_trend_row("AI혁명", "korea", 85, 3.0),
            _make_trend_row("반도체 전쟁", "korea", 75, 2.0),
            _make_trend_row("Super Bowl", "united-states", 90, 1.0),
        ]
        conn = _mock_conn_with_trends(trends)
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()

        assert len(result) >= 2
        keywords = [o.keyword for o in result]
        assert any("AI" in kw or "반도체" in kw for kw in keywords)

    @pytest.mark.asyncio
    async def test_same_keyword_both_countries_no_opportunity(self):
        """양쪽 국가에 같은 키워드가 있으면 기회 없음."""
        from tap.detector import TrendArbitrageDetector
        trends = [
            _make_trend_row("Bitcoin", "korea", 80, 3.0),
            _make_trend_row("Bitcoin", "united-states", 85, 1.0),
        ]
        conn = _mock_conn_with_trends(trends)
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()

        bitcoin_opps = [o for o in result if "bitcoin" in o.keyword.lower()]
        assert len(bitcoin_opps) == 0

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """priority가 높은 순서로 반환."""
        from tap.detector import TrendArbitrageDetector
        trends = [
            _make_trend_row("낮은점수", "korea", 60, 3.0),
            _make_trend_row("높은점수", "korea", 95, 5.0),
            _make_trend_row("미국트렌드", "united-states", 70, 2.0),
        ]
        conn = _mock_conn_with_trends(trends)
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()

        if len(result) >= 2:
            assert result[0].priority >= result[1].priority

    @pytest.mark.asyncio
    async def test_db_error_graceful(self):
        """DB 에러 시 빈 결과 반환 (파이프라인 중단 없음)."""
        from tap.detector import TrendArbitrageDetector
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=RuntimeError("DB 접속 실패"))
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()
        assert result == []

    @pytest.mark.asyncio
    async def test_max_opportunities_limit(self):
        """최대 반환 수 제한."""
        from tap.detector import TrendArbitrageDetector
        trends = []
        for i in range(15):
            trends.append(_make_trend_row(f"키워드_{i}", "korea", 80 + i, 3.0))
        trends.append(_make_trend_row("US트렌드", "united-states", 70, 2.0))

        conn = _mock_conn_with_trends(trends)
        detector = TrendArbitrageDetector(conn)
        result = await detector.detect()
        assert len(result) <= TrendArbitrageDetector.MAX_OPPORTUNITIES


# ══════════════════════════════════════════════════════
#  Analyzer Tests
# ══════════════════════════════════════════════════════

class TestArbitrageAnalyzer:
    """차익거래 분석기 테스트."""

    def test_empty_opportunities_returns_empty_block(self):
        from tap.analyzer import ArbitrageAnalyzer
        analyzer = ArbitrageAnalyzer([])
        assert analyzer.to_prompt_block() == ""
        assert analyzer.count == 0

    def test_none_opportunities_returns_empty_block(self):
        from tap.analyzer import ArbitrageAnalyzer
        analyzer = ArbitrageAnalyzer(None)
        assert analyzer.to_prompt_block() == ""

    def test_prompt_block_generation(self):
        from tap.analyzer import ArbitrageAnalyzer
        from tap.detector import ArbitrageOpportunity

        opps = [
            ArbitrageOpportunity(
                keyword="AI혁명",
                source_country="korea",
                target_countries=["united-states", "japan"],
                viral_score=85,
                time_gap_hours=4.5,
                priority=72.5,
            ),
        ]
        analyzer = ArbitrageAnalyzer(opps)
        block = analyzer.to_prompt_block()
        assert "TAP" in block
        assert "AI혁명" in block
        assert "KOREA" in block
        assert "선점" in block

    def test_filter_for_country(self):
        from tap.analyzer import ArbitrageAnalyzer
        from tap.detector import ArbitrageOpportunity

        opps = [
            ArbitrageOpportunity(
                keyword="트렌드A",
                source_country="korea",
                target_countries=["united-states"],
                viral_score=80,
                priority=60.0,
            ),
            ArbitrageOpportunity(
                keyword="트렌드B",
                source_country="japan",
                target_countries=["korea"],
                viral_score=75,
                priority=55.0,
            ),
        ]
        analyzer = ArbitrageAnalyzer(opps)

        us_opps = analyzer.filter_for_country("united-states")
        assert len(us_opps) == 1
        assert us_opps[0].keyword == "트렌드A"

        kr_opps = analyzer.filter_for_country("korea")
        assert len(kr_opps) == 1
        assert kr_opps[0].keyword == "트렌드B"

    def test_log_summary_no_error(self):
        """log_summary가 에러 없이 실행되는지 확인."""
        from tap.analyzer import ArbitrageAnalyzer
        from tap.detector import ArbitrageOpportunity

        opps = [
            ArbitrageOpportunity(
                keyword="테스트",
                source_country="korea",
                target_countries=["japan"],
                viral_score=80,
                time_gap_hours=3.0,
                priority=65.0,
            ),
        ]
        analyzer = ArbitrageAnalyzer(opps)
        analyzer.log_summary()


# ══════════════════════════════════════════════════════
#  Entry Point Tests
# ══════════════════════════════════════════════════════

class TestEntryPoint:
    """패키지 진입점 테스트."""

    @pytest.mark.asyncio
    async def test_detect_arbitrage_opportunities(self):
        """convenience function이 정상 동작."""
        from tap import detect_arbitrage_opportunities

        trends = [
            _make_trend_row("테스트키워드", "korea", 80, 3.0),
            _make_trend_row("USonly", "united-states", 75, 2.0),
        ]
        conn = _mock_conn_with_trends(trends)
        result = await detect_arbitrage_opportunities(conn)
        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_detect_with_config(self):
        """config 전달 시 정상 동작."""
        from tap import detect_arbitrage_opportunities

        mock_config = MagicMock()
        mock_config.countries = ["korea", "united-states"]

        trends = [
            _make_trend_row("한국전용", "korea", 85, 4.0),
            _make_trend_row("미국전용", "united-states", 90, 1.0),
        ]
        conn = _mock_conn_with_trends(trends)
        result = await detect_arbitrage_opportunities(conn, config=mock_config)
        assert isinstance(result, list)
