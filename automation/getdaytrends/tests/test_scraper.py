"""scraper.py 테스트: 볼륨 파싱, 캐시, 중복 필터."""

import os
import unittest

from models import RawTrend, TrendSource
from scraper import (
    _FETCH_CACHE,
    _FETCH_CACHE_TTL,
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


if __name__ == "__main__":
    unittest.main()
