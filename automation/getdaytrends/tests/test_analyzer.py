"""analyzer.py 테스트: JSON 파싱, 기본값 폴백, 패턴 감지."""

import sqlite3
import unittest

from analyzer import _parse_json_array, _parse_json
from models import MultiSourceContext, ScoredTrend


class TestParseJson(unittest.TestCase):
    """Claude structured output JSON 파싱 (v2.2 _parse_json)."""

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
        result = _parse_json("not json at all")
        self.assertIsNone(result)

    def test_empty_string(self):
        result = _parse_json("")
        self.assertIsNone(result)

    def test_none_input(self):
        result = _parse_json(None)
        self.assertIsNone(result)


class TestParseJsonArray(unittest.TestCase):
    """클러스터링 응답 JSON 배열 파싱."""

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
        result = _parse_json_array("no array here")
        self.assertIsNone(result)

    def test_multiple_groups(self):
        text = """[
            {"representative": "AI", "members": ["AI", "GPT"]},
            {"representative": "정치", "members": ["정치"]}
        ]"""
        result = _parse_json_array(text)
        self.assertEqual(len(result), 2)


class TestDefaultScoredTrend(unittest.TestCase):
    """스코어링 실패 시 기본값."""

    def test_default_values(self):
        from analyzer import _default_scored_trend

        ctx = MultiSourceContext()
        trend = _default_scored_trend("테스트", ctx)
        self.assertEqual(trend.keyword, "테스트")
        self.assertEqual(trend.viral_potential, 0)
        self.assertEqual(trend.rank, 0)


class TestDetectTrendPatterns(unittest.IsolatedAsyncioTestCase):
    """히스토리 기반 패턴 감지."""

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
        pattern = await detect_trend_patterns(self.conn, "없는키워드")
        self.assertEqual(pattern["seen_count"], 0)
        self.assertFalse(pattern["is_recurring"])
        self.assertEqual(pattern["score_trend"], "new")

    async def test_with_history(self):
        from analyzer import detect_trend_patterns
        from db import save_trend
        from models import ScoredTrend, TrendSource

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


# ══════════════════════════════════════════════════════
#  v4.0 신규 테스트: Phase 1~4 검증
# ══════════════════════════════════════════════════════

class TestCrossSourceConfidence(unittest.TestCase):
    """Phase 1: 멀티소스 교차 검증 점수 계산."""

    def _conf(self, volume=0, twitter="", news="", reddit=""):
        from analyzer import _compute_cross_source_confidence
        ctx = MultiSourceContext(twitter_insight=twitter, news_insight=news, reddit_insight=reddit)
        return _compute_cross_source_confidence(volume, ctx)

    def test_zero_all_empty(self):
        self.assertEqual(self._conf(), 0)

    def test_volume_only(self):
        self.assertEqual(self._conf(volume=10000), 1)

    def test_volume_plus_twitter(self):
        score = self._conf(volume=5000, twitter="트위터 실시간 반응 내용이 충분히 긴 문자열")
        self.assertEqual(score, 2)

    def test_full_four_sources(self):
        score = self._conf(
            volume=50000,
            twitter="트위터 실시간 반응 내용이 충분히 긴 문자열입니다",
            news="뉴스 헤드라인이 충분히 긴 문자열입니다",
            reddit="레딧 게시물이 충분히 긴 문자열입니다 내용 있음",
        )
        self.assertEqual(score, 4)

    def test_error_text_ignored(self):
        """'오류' 포함 Twitter 데이터는 점수 없음."""
        score = self._conf(volume=1000, twitter="[X 데이터 없음] 키워드 오류 발생")
        self.assertEqual(score, 1)  # volume만

    def test_none_context(self):
        from analyzer import _compute_cross_source_confidence
        score = _compute_cross_source_confidence(0, None)
        self.assertEqual(score, 0)


class TestSignalScore(unittest.TestCase):
    """Phase 2: 시그널 기반 보조 점수 계산."""

    def _sig(self, vol=0, acc="+0%", conf=0, is_new=True):
        from analyzer import _compute_signal_score
        return _compute_signal_score(vol, acc, conf, is_new)

    def test_zero_everything(self):
        score = self._sig()
        # 신선도(20) + 나머지 0
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
    """Phase 1~4: _parse_scored_trend_from_dict 검증."""

    def _make_parsed(self, **kwargs):
        base = {
            "keyword": "테스트",
            "volume_last_24h": 50000,
            "trend_acceleration": "+15%",
            "viral_potential": 80,
            "top_insight": "핵심 인사이트",
            "suggested_angles": ["앵글1", "앵글2"],
            "best_hook_starter": "이것이 훅",
            "category": "테크",
            "sentiment": "neutral",
            "safety_flag": False,
            "joongyeon_kick": 85,
            "joongyeon_angle": "AI가 직업 뺏는다지만 이미 자동화된 거였다",
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
        result = _parse_scored_trend_from_dict(parsed, "테스트", 50000, ctx)
        self.assertEqual(result.joongyeon_kick, 85)
        self.assertEqual(result.joongyeon_angle, "AI가 직업 뺏는다지만 이미 자동화된 거였다")

    def test_joongyeon_kick_clamped(self):
        from analyzer import _parse_scored_trend_from_dict
        ctx = MultiSourceContext()
        parsed = self._make_parsed(joongyeon_kick=150)
        result = _parse_scored_trend_from_dict(parsed, "테스트", 50000, ctx)
        self.assertLessEqual(result.joongyeon_kick, 100)

    def test_low_confidence_penalty(self):
        """cross_source_confidence < 2 → viral_potential × 0.65."""
        from analyzer import _parse_scored_trend_from_dict
        ctx = MultiSourceContext()  # 모든 소스 비어있음 → confidence = 0
        parsed = self._make_parsed(viral_potential=80, joongyeon_kick=0)
        result = _parse_scored_trend_from_dict(parsed, "테스트", 0, ctx)
        # confidence=0 → 패널티 적용됨 → 원래 80점보다 낮아야 함
        self.assertLess(result.viral_potential, 80)

    def test_high_confidence_no_penalty(self):
        """cross_source_confidence >= 2 → 패널티 없음."""
        from analyzer import _parse_scored_trend_from_dict
        ctx = MultiSourceContext(
            twitter_insight="x" * 30,
            news_insight="y" * 30,
        )  # confidence = 2 (볼륨 없어도 X+뉴스)
        parsed = self._make_parsed(viral_potential=80)
        result = _parse_scored_trend_from_dict(parsed, "테스트", 1000, ctx)
        # 패널티 없음 → 점수가 크게 낮아지지 않아야 함 (하이브리드 가중치 적용됨)
        self.assertGreater(result.viral_potential, 40)

    def test_cross_source_confidence_field_set(self):
        from analyzer import _parse_scored_trend_from_dict
        ctx = MultiSourceContext(twitter_insight="충분히 긴 트위터 내용입니다", news_insight="충분히 긴 뉴스 내용입니다")
        parsed = self._make_parsed()
        result = _parse_scored_trend_from_dict(parsed, "테스트", 5000, ctx)
        self.assertGreaterEqual(result.cross_source_confidence, 0)
        self.assertLessEqual(result.cross_source_confidence, 4)


if __name__ == "__main__":
    unittest.main()
