"""scraper.py 테스트: 볼륨 파싱, 캐시, 중복 필터."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock

import httpx
from models import RawTrend, TrendSource
from scraper import (
    _FETCH_CACHE,
    _FETCH_CACHE_TTL,
    _async_fetch_getdaytrends,
    _async_fetch_google_trends_rss,
    _is_korean_trend,
    _is_similar_keyword,
    _merge_trends,
    _parse_volume_text,
)


class TestParseVolumeText(unittest.TestCase):
    """getdaytrends.com 볼륨 문자열 → 숫자 변환."""

    def test_simple_k(self):
        self.assertEqual(_parse_volume_text("50K+"), 50_000)

    def test_simple_m(self):
        self.assertEqual(_parse_volume_text("1M"), 1_000_000)

    def test_decimal_k(self):
        self.assertEqual(_parse_volume_text("2.5K"), 2_500)

    def test_under_10k(self):
        self.assertEqual(_parse_volume_text("<10K"), 9_999)

    def test_under_with_word(self):
        self.assertEqual(_parse_volume_text("Under 10K"), 9_999)

    def test_na(self):
        self.assertEqual(_parse_volume_text("N/A"), 0)

    def test_empty(self):
        self.assertEqual(_parse_volume_text(""), 0)

    def test_plain_number(self):
        self.assertEqual(_parse_volume_text("500"), 500)

    def test_with_comma(self):
        self.assertEqual(_parse_volume_text("1,000"), 1_000)

    def test_billion(self):
        self.assertEqual(_parse_volume_text("1B"), 1_000_000_000)

    def test_whitespace(self):
        self.assertEqual(_parse_volume_text("  50K  "), 50_000)

    def test_lowercase(self):
        self.assertEqual(_parse_volume_text("50k"), 50_000)


class TestSimilarKeyword(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(_is_similar_keyword("ai", {"ai"}))

    def test_substring_forward(self):
        self.assertTrue(_is_similar_keyword("ChatGPT 업데이트", {"chatgpt"}))

    def test_no_match(self):
        self.assertFalse(_is_similar_keyword("날씨", {"chatgpt", "bts"}))

    def test_short_keyword_no_partial(self):
        # 2자 이하는 부분 매칭 안 함 (오탐 방지)
        self.assertFalse(_is_similar_keyword("AI", {"chatgpt-ai"}))


class TestKoreanFilter(unittest.TestCase):
    def test_hangul_allowed(self):
        self.assertTrue(_is_korean_trend("오늘날씨", "korea"))

    def test_ascii_allowed_for_korea(self):
        self.assertTrue(_is_korean_trend("BTS", "korea"))

    def test_non_korean_filtered(self):
        self.assertFalse(_is_korean_trend("東京オリンピック", "korea"))

    def test_non_korea_country_passthrough(self):
        self.assertTrue(_is_korean_trend("東京オリンピック", "japan"))

    def test_single_char_rejected(self):
        self.assertFalse(_is_korean_trend("A", "korea"))


class TestMergeTrends(unittest.TestCase):
    def _t(self, name: str) -> RawTrend:
        return RawTrend(name=name, source=TrendSource.GETDAYTRENDS)

    def test_case_insensitive_dedup(self):
        primary = [self._t("BTS")]
        secondary = [self._t("bts"), self._t("뉴진스")]
        merged = _merge_trends(primary, secondary, limit=10)
        self.assertEqual(sum(1 for t in merged if t.name.lower() == "bts"), 1)

    def test_limit_applied(self):
        # 임베딩 비활성화 (문자열 기반 limit 로직만 검증)
        orig_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            # shared.embeddings 내부 클라이언트 초기화 리셋
            try:
                import shared.embeddings.core as _ecore

                _ecore._client = None
            except ImportError:
                pass
            primary = [self._t(f"trend{i}") for i in range(20)]
            merged = _merge_trends(primary, [], limit=5)
            self.assertEqual(len(merged), 5)
        finally:
            if orig_key is not None:
                os.environ["GOOGLE_API_KEY"] = orig_key

    def test_primary_preferred_over_secondary(self):
        primary = [self._t("AI Agent")]
        secondary = [self._t("ai agent")]
        merged = _merge_trends(primary, secondary, limit=5)
        self.assertEqual(merged[0].name, "AI Agent")


class TestFetchCache(unittest.TestCase):
    def setUp(self):
        _FETCH_CACHE.clear()

    def tearDown(self):
        _FETCH_CACHE.clear()

    def test_cache_key_stored(self):
        import time as _time

        trends = [RawTrend(name="테스트", source=TrendSource.GETDAYTRENDS)]
        _FETCH_CACHE["korea"] = (_time.time(), trends)
        self.assertIn("korea", _FETCH_CACHE)
        self.assertEqual(len(_FETCH_CACHE["korea"][1]), 1)

    def test_cache_expired_detection(self):
        import time as _time

        expired_ts = _time.time() - _FETCH_CACHE_TTL - 1
        _FETCH_CACHE["us"] = (expired_ts, [])
        cached_at, _ = _FETCH_CACHE["us"]
        self.assertGreater(_time.time() - cached_at, _FETCH_CACHE_TTL)

    def test_x_cache_ttl_is_ninety_seconds(self):
        self.assertEqual(_FETCH_CACHE_TTL, 90)


class TestGetDayTrendsRefreshContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _FETCH_CACHE.clear()

    def tearDown(self):
        _FETCH_CACHE.clear()

    async def test_regular_refresh_reuses_recent_cache(self):
        import time as _time

        cached = [RawTrend(name="기존 X 단어", source=TrendSource.GETDAYTRENDS)]
        _FETCH_CACHE["korea"] = (_time.time(), cached)
        session = MagicMock()
        session.get = AsyncMock()

        result = await _async_fetch_getdaytrends(session, "korea", 20)

        self.assertEqual(result[0].name, "기존 X 단어")
        self.assertTrue(result[0].extra["_getdaytrends_sample_id"].startswith("korea:"))
        session.get.assert_not_awaited()

    async def test_manual_force_refresh_bypasses_recent_cache(self):
        import time as _time

        _FETCH_CACHE["korea"] = (
            _time.time(),
            [RawTrend(name="기존 X 단어", source=TrendSource.GETDAYTRENDS)],
        )
        request = httpx.Request("GET", "https://getdaytrends.com/korea/")
        response = httpx.Response(
            200,
            text='<table class="trends"><tbody><tr><td class="main"><a href="/korea/trend/new/">새 X 단어</a></td></tr></tbody></table>',
            request=request,
        )
        session = MagicMock()
        session.get = AsyncMock(return_value=response)

        result = await _async_fetch_getdaytrends(session, "korea", 20, force_refresh=True)

        self.assertEqual(result[0].name, "새 X 단어")
        session.get.assert_awaited_once()

    async def test_failed_force_refresh_uses_last_observed_cache(self):
        import time as _time

        _FETCH_CACHE["korea"] = (
            _time.time(),
            [RawTrend(name="마지막 확인 단어", source=TrendSource.GETDAYTRENDS)],
        )
        request = httpx.Request("GET", "https://getdaytrends.com/korea/")
        session = MagicMock()
        session.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out", request=request))

        result = await _async_fetch_getdaytrends(session, "korea", 20, force_refresh=True)

        self.assertEqual(result[0].name, "마지막 확인 단어")


class TestGoogleTrendsRssResilience(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_direct_news_source_urls(self):
        request = httpx.Request("GET", "https://trends.google.com/trending/rss?geo=KR")
        response = httpx.Response(
            200,
            text="""<?xml version="1.0" encoding="UTF-8"?>
            <rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item>
              <title>속보 키워드</title><ht:approx_traffic>5000+</ht:approx_traffic>
              <link>https://trends.google.com/trending/rss?geo=KR</link>
              <pubDate>Wed, 5 Aug 2026 01:40:00 -0700</pubDate>
              <ht:news_item>
                <ht:news_item_title>직접 확인할 기사</ht:news_item_title>
                <ht:news_item_url>https://news.example.com/original</ht:news_item_url>
                <ht:news_item_source>테스트뉴스</ht:news_item_source>
              </ht:news_item>
            </item></channel></rss>""",
            request=request,
        )
        session = MagicMock()
        session.get = AsyncMock(return_value=response)

        trends = await _async_fetch_google_trends_rss(session, "korea", limit=5)

        self.assertEqual(
            trends[0].extra["news_items"],
            [{"title": "직접 확인할 기사", "url": "https://news.example.com/original", "source": "테스트뉴스"}],
        )

    async def test_returns_empty_on_http_status_error(self):
        request = httpx.Request("GET", "https://trends.google.com/trending/rss?geo=US")
        response = httpx.Response(
            404,
            text="<html><body>not found</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )
        session = MagicMock()
        session.get = AsyncMock(return_value=response)

        trends = await _async_fetch_google_trends_rss(session, "united-states", limit=5)

        self.assertEqual(trends, [])

    async def test_returns_empty_on_unexpected_root_tag(self):
        request = httpx.Request("GET", "https://trends.google.com/trending/rss?geo=US")
        response = httpx.Response(
            200,
            text="<html><body>ok but not rss</body></html>",
            headers={"content-type": "text/html"},
            request=request,
        )
        session = MagicMock()
        session.get = AsyncMock(return_value=response)

        trends = await _async_fetch_google_trends_rss(session, "united-states", limit=5)

        self.assertEqual(trends, [])

    async def test_returns_empty_on_timeout(self):
        request = httpx.Request("GET", "https://trends.google.com/trending/rss?geo=US")
        session = MagicMock()
        session.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out", request=request))

        trends = await _async_fetch_google_trends_rss(session, "united-states", limit=5)

        self.assertEqual(trends, [])


if __name__ == "__main__":
    unittest.main()
