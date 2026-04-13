"""Tests for analyzer parsing, scoring helpers, and batch isolation."""

import unittest
from unittest.mock import AsyncMock, patch

from analyzer import _parse_json, _parse_json_array
from models import MultiSourceContext, RawTrend, ScoredTrend, TrendSource


class TestParseJson(unittest.TestCase):
    def test_clean_json(self):
        text = '{"keyword": "test", "viral_potential": 85}'
        result = _parse_json(text)
        self.assertEqual(result["keyword"], "test")
        self.assertEqual(result["viral_potential"], 85)

    def test_whitespace_padding(self):
        text = '  {"keyword": "AI", "viral_potential": 90}  '
        result = _parse_json(text)
        self.assertEqual(result["keyword"], "AI")

    def test_invalid_json(self):
        self.assertIsNone(_parse_json("not json at all"))

    def test_empty_string(self):
        self.assertIsNone(_parse_json(""))

    def test_none_input(self):
        self.assertIsNone(_parse_json(None))


class TestParseJsonArray(unittest.TestCase):
    def test_clean_array(self):
        text = '[{"representative": "AI", "members": ["AI", "ChatGPT"]}]'
        result = _parse_json_array(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["representative"], "AI")

    def test_whitespace_padded_array(self):
        text = '  [{"representative": "test", "members": ["test"]}]  '
        result = _parse_json_array(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_invalid_array(self):
        self.assertIsNone(_parse_json_array("no array here"))

    def test_multiple_groups(self):
        text = """
        [
            {"representative": "AI", "members": ["AI", "GPT"]},
            {"representative": "politics", "members": ["politics"]}
        ]
        """
        result = _parse_json_array(text)
        self.assertEqual(len(result), 2)


class TestDefaultScoredTrend(unittest.TestCase):
    def test_default_values(self):
        from analyzer import _default_scored_trend

        ctx = MultiSourceContext()
        trend = _default_scored_trend("test", ctx)
        self.assertEqual(trend.keyword, "test")
        self.assertEqual(trend.viral_potential, 0)
        self.assertEqual(trend.rank, 0)


class TestDetectTrendPatterns(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import aiosqlite

        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        from db import init_db

        await init_db(self.conn)

    async def asyncTearDown(self):
        await self.conn.close()

    async def test_no_history(self):
        from analyzer import detect_trend_patterns

        pattern = await detect_trend_patterns(self.conn, "missing")
        self.assertEqual(pattern["seen_count"], 0)
        self.assertFalse(pattern["is_recurring"])
        self.assertEqual(pattern["score_trend"], "new")

    async def test_with_history(self):
        from analyzer import detect_trend_patterns
        from db import save_trend

        t1 = ScoredTrend(keyword="AI", rank=1, viral_potential=50, sources=[TrendSource.GETDAYTRENDS])
        await save_trend(self.conn, t1, 1)

        t2 = ScoredTrend(keyword="AI", rank=2, viral_potential=60, sources=[TrendSource.GETDAYTRENDS])
        await save_trend(self.conn, t2, 2)

        t3 = ScoredTrend(keyword="AI", rank=1, viral_potential=80, sources=[TrendSource.GETDAYTRENDS])
        await save_trend(self.conn, t3, 3)

        pattern = await detect_trend_patterns(self.conn, "AI")
        self.assertEqual(pattern["seen_count"], 3)
        self.assertTrue(pattern["is_recurring"])
        self.assertGreater(pattern["avg_score"], 0)


class TestCrossSourceConfidence(unittest.TestCase):
    def _conf(self, volume=0, twitter="", news="", reddit=""):
        from analyzer import _compute_cross_source_confidence

        ctx = MultiSourceContext(twitter_insight=twitter, news_insight=news, reddit_insight=reddit)
        return _compute_cross_source_confidence(volume, ctx)

    def test_zero_all_empty(self):
        self.assertEqual(self._conf(), 0)

    def test_volume_only(self):
        self.assertEqual(self._conf(volume=10000), 1)

    def test_volume_plus_twitter(self):
        score = self._conf(volume=5000, twitter="twitter context with enough detail")
        self.assertEqual(score, 2)

    def test_full_four_sources(self):
        score = self._conf(
            volume=50000,
            twitter="twitter context with enough detail to count",
            news="news context with enough detail to count",
            reddit="reddit context with enough detail to count",
        )
        self.assertEqual(score, 4)

    def test_error_text_ignored(self):
        score = self._conf(volume=1000, twitter="[X error] failed to fetch")
        self.assertEqual(score, 2)

    def test_none_context(self):
        from analyzer import _compute_cross_source_confidence

        self.assertEqual(_compute_cross_source_confidence(0, None), 0)


class TestSignalScore(unittest.TestCase):
    def _sig(self, vol=0, acc="+0%", conf=0, is_new=True):
        from analyzer import _compute_signal_score

        return _compute_signal_score(vol, acc, conf, is_new)

    def test_zero_everything(self):
        score = self._sig()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_high_volume_boosts_score(self):
        low = self._sig(vol=100)
        high = self._sig(vol=1_000_000)
        self.assertGreater(high, low)

    def test_high_acceleration_boosts(self):
        base = self._sig(vol=10000, acc="+1%")
        accel = self._sig(vol=10000, acc="+35%")
        self.assertGreater(accel, base)

    def test_negative_acceleration_zero(self):
        score = self._sig(vol=10000, acc="-10%")
        baseline = self._sig(vol=10000, acc="+0%")
        self.assertLessEqual(score, baseline)

    def test_full_confidence_adds_max_20(self):
        no_conf = self._sig(vol=0, acc="+0%", conf=0)
        full_conf = self._sig(vol=0, acc="+0%", conf=4)
        self.assertAlmostEqual(full_conf - no_conf, 20.0, places=0)

    def test_capped_at_100(self):
        score = self._sig(vol=10_000_000, acc="+100%", conf=4, is_new=True)
        self.assertLessEqual(score, 100)


class TestParseScoredTrendV4(unittest.TestCase):
    def _make_parsed(self, **kwargs):
        base = {
            "keyword": "test-keyword",
            "volume_last_24h": 50000,
            "trend_acceleration": "+15%",
            "viral_potential": 80,
            "top_insight": "key insight",
            "suggested_angles": ["angle1", "angle2"],
            "best_hook_starter": "strong hook",
            "category": "tech",
            "sentiment": "neutral",
            "safety_flag": False,
            "joongyeon_kick": 85,
            "joongyeon_angle": "angle framing",
        }
        base.update(kwargs)
        return base

    def test_joongyeon_kick_parsed(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext(
            twitter_insight="x" * 30,
            news_insight="y" * 30,
            reddit_insight="z" * 30,
        )
        parsed = self._make_parsed()
        result = _parse_scored_trend_from_dict(parsed, "test-keyword", 50000, ctx)
        self.assertEqual(result.joongyeon_kick, 85)
        self.assertEqual(result.joongyeon_angle, "angle framing")

    def test_joongyeon_kick_clamped(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext()
        parsed = self._make_parsed(joongyeon_kick=150)
        result = _parse_scored_trend_from_dict(parsed, "test-keyword", 50000, ctx)
        self.assertLessEqual(result.joongyeon_kick, 100)

    def test_low_confidence_penalty(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext()
        parsed = self._make_parsed(viral_potential=80, joongyeon_kick=0)
        result = _parse_scored_trend_from_dict(parsed, "test-keyword", 0, ctx)
        self.assertLess(result.viral_potential, 80)

    def test_high_confidence_no_penalty(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext(
            twitter_insight="x" * 30,
            news_insight="y" * 30,
        )
        parsed = self._make_parsed(viral_potential=80)
        result = _parse_scored_trend_from_dict(parsed, "test-keyword", 1000, ctx)
        self.assertGreater(result.viral_potential, 40)

    def test_cross_source_confidence_field_set(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext(
            twitter_insight="enough twitter context",
            news_insight="enough news context",
        )
        parsed = self._make_parsed()
        result = _parse_scored_trend_from_dict(parsed, "test-keyword", 5000, ctx)
        self.assertGreaterEqual(result.cross_source_confidence, 0)
        self.assertLessEqual(result.cross_source_confidence, 4)

    def test_nullable_optional_fields_fall_back_to_defaults(self):
        from analyzer import _parse_scored_trend_from_dict

        ctx = MultiSourceContext()
        parsed = self._make_parsed(
            volume_last_24h=None,
            trend_acceleration=None,
            top_insight=None,
            suggested_angles=None,
            best_hook_starter=None,
            sentiment=None,
            joongyeon_kick=None,
            joongyeon_angle=None,
            why_trending=None,
            peak_status=None,
            relevance_score=None,
        )
        result = _parse_scored_trend_from_dict(parsed, "test-nullable", 50000, ctx)

        self.assertEqual(result.volume_last_24h, 50000)
        self.assertEqual(result.trend_acceleration, "+0%")
        self.assertEqual(result.top_insight, "")
        self.assertEqual(result.suggested_angles, [])
        self.assertEqual(result.best_hook_starter, "")
        self.assertEqual(result.sentiment, "neutral")
        self.assertEqual(result.joongyeon_kick, 0)
        self.assertEqual(result.joongyeon_angle, "")
        self.assertEqual(result.why_trending, "")
        self.assertEqual(result.peak_status, "")
        self.assertEqual(result.relevance_score, 0)


class TestBatchScoreIsolation(unittest.IsolatedAsyncioTestCase):
    async def test_batch_score_async_recovers_only_malformed_item(self):
        from analyzer import _batch_score_async

        bad_context = MultiSourceContext(twitter_insight="bad context")
        good_context = MultiSourceContext(news_insight="good context")
        batch = [
            (
                RawTrend(
                    name="trendbad",
                    source=TrendSource.GETDAYTRENDS,
                    volume="1000",
                    volume_numeric=1000,
                ),
                bad_context,
            ),
            (
                RawTrend(
                    name="trendgood",
                    source=TrendSource.GETDAYTRENDS,
                    volume="2000",
                    volume_numeric=2000,
                ),
                good_context,
            ),
        ]
        parsed_list = [
            {
                "viral_potential": "N/A",
                "trend_acceleration": "+10%",
                "top_insight": "bad item",
                "joongyeon_kick": 0,
                "relevance_score": 5,
            },
            {
                "viral_potential": 81,
                "trend_acceleration": "+22%",
                "top_insight": "good item",
                "suggested_angles": ["angle"],
                "best_hook_starter": "hook",
                "category": "tech",
                "sentiment": "neutral",
                "safety_flag": False,
                "joongyeon_kick": 12,
                "joongyeon_angle": "",
                "why_trending": "",
                "peak_status": "rising",
                "relevance_score": 7,
            },
        ]
        recovered = ScoredTrend(
            keyword="trendbad",
            rank=0,
            viral_potential=42,
            context=bad_context,
            sources=[TrendSource.GETDAYTRENDS],
        )

        with (
            patch("analyzer._score_batch_instructor", new_callable=AsyncMock, return_value=parsed_list),
            patch("analyzer._score_trend_async", new_callable=AsyncMock, return_value=recovered) as mock_recover,
        ):
            results = await _batch_score_async(batch, client=object(), conn=None, config=None, bucket=5000)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].keyword, "trendbad")
        self.assertEqual(results[0].viral_potential, 42)
        self.assertEqual(results[1].keyword, "trendgood")
        self.assertGreater(results[1].viral_potential, 0)
        mock_recover.assert_awaited_once()

    async def test_batch_score_async_nullable_fields_do_not_trigger_recovery(self):
        from analyzer import _batch_score_async

        context = MultiSourceContext(news_insight="good context")
        batch = [
            (
                RawTrend(
                    name="trendnull",
                    source=TrendSource.GETDAYTRENDS,
                    volume="1000",
                    volume_numeric=1000,
                ),
                context,
            ),
        ]
        parsed_list = [
            {
                "viral_potential": 12,
                "publishable": False,
                "publishability_reason": "meaningless keyword",
                "volume_last_24h": None,
                "trend_acceleration": None,
                "top_insight": None,
                "suggested_angles": None,
                "best_hook_starter": None,
                "sentiment": None,
                "joongyeon_kick": None,
                "joongyeon_angle": None,
                "why_trending": None,
                "peak_status": None,
                "relevance_score": None,
            },
        ]

        with (
            patch("analyzer._score_batch_instructor", new_callable=AsyncMock, return_value=parsed_list),
            patch("analyzer._score_trend_async", new_callable=AsyncMock) as mock_recover,
        ):
            results = await _batch_score_async(batch, client=object(), conn=None, config=None, bucket=5000)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].keyword, "trendnull")
        self.assertEqual(results[0].volume_last_24h, 1000)
        self.assertEqual(results[0].trend_acceleration, "+0%")
        self.assertFalse(results[0].publishable)
        mock_recover.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
