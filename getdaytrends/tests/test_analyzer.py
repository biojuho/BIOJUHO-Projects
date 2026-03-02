"""analyzer.py 테스트: JSON 파싱, 기본값 폴백, 패턴 감지."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import _parse_json_array, _robust_json_parse
from models import MultiSourceContext, ScoredTrend


class TestRobustJsonParse(unittest.TestCase):
    """Claude 응답에서 JSON 객체 추출."""

    def test_clean_json(self):
        text = '{"keyword": "test", "viral_potential": 85}'
        result = _robust_json_parse(text)
        self.assertEqual(result["keyword"], "test")
        self.assertEqual(result["viral_potential"], 85)

    def test_markdown_wrapped(self):
        text = '```json\n{"keyword": "AI", "viral_potential": 90}\n```'
        result = _robust_json_parse(text)
        self.assertEqual(result["keyword"], "AI")

    def test_trailing_comma(self):
        text = '{"keyword": "test", "angles": ["a", "b",]}'
        result = _robust_json_parse(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["keyword"], "test")

    def test_text_before_json(self):
        text = 'Here is the analysis:\n\n{"keyword": "test", "viral_potential": 75}'
        result = _robust_json_parse(text)
        self.assertEqual(result["viral_potential"], 75)

    def test_invalid_json(self):
        result = _robust_json_parse("not json at all")
        self.assertIsNone(result)

    def test_empty_string(self):
        result = _robust_json_parse("")
        self.assertIsNone(result)


class TestParseJsonArray(unittest.TestCase):
    """클러스터링 응답 JSON 배열 파싱."""

    def test_clean_array(self):
        text = '[{"representative": "AI", "members": ["AI", "ChatGPT"]}]'
        result = _parse_json_array(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["representative"], "AI")

    def test_markdown_wrapped_array(self):
        text = '```json\n[{"representative": "test", "members": ["test"]}]\n```'
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


class TestDetectTrendPatterns(unittest.TestCase):
    """히스토리 기반 패턴 감지."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from db import init_db
        init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_no_history(self):
        from analyzer import detect_trend_patterns
        pattern = detect_trend_patterns(self.conn, "없는키워드")
        self.assertEqual(pattern["seen_count"], 0)
        self.assertFalse(pattern["is_recurring"])
        self.assertEqual(pattern["score_trend"], "new")

    def test_with_history(self):
        from analyzer import detect_trend_patterns
        from datetime import datetime

        # 테스트 데이터 삽입
        run_id = self.conn.execute(
            "INSERT INTO runs (run_uuid, started_at, country) VALUES ('test', ?, 'korea')",
            (datetime.now().isoformat(),)
        ).lastrowid
        self.conn.commit()

        for score in [60, 70, 80]:
            self.conn.execute(
                """INSERT INTO trends (run_id, keyword, rank, viral_potential, scored_at)
                   VALUES (?, 'AI', 1, ?, ?)""",
                (run_id, score, datetime.now().isoformat()),
            )
        self.conn.commit()

        pattern = detect_trend_patterns(self.conn, "AI")
        self.assertEqual(pattern["seen_count"], 3)
        self.assertTrue(pattern["is_recurring"])
        self.assertGreater(pattern["avg_score"], 0)


if __name__ == "__main__":
    unittest.main()
