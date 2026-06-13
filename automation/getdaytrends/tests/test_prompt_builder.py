import unittest

from models import MultiSourceContext, ScoredTrend, TrendContext
from prompt_builder import _build_fact_guardrail_section, _build_revision_feedback_section, _parse_json


class TestPromptBuilderParseJson(unittest.TestCase):
    def test_parse_json_returns_dict(self):
        data = _parse_json('{"topic":"AI","count":1}')
        self.assertEqual(data, {"topic": "AI", "count": 1})

    def test_parse_json_accepts_markdown_fence(self):
        data = _parse_json('```json\n{"topic":"AI","count":1}\n```')
        self.assertEqual(data, {"topic": "AI", "count": 1})

    def test_parse_json_repairs_trailing_commas(self):
        raw = """
        {
          "topic": "AI",
          "context_analysis": {
            "pattern": "search spike",
          },
          "tweets": [
            {"type": "hook", "content": "value",},
          ],
        }
        """

        data = _parse_json(raw)

        self.assertEqual(data["context_analysis"]["pattern"], "search spike")
        self.assertEqual(data["tweets"][0]["content"], "value")

    def test_parse_json_does_not_repair_commas_inside_strings(self):
        data = _parse_json('{"topic":"AI","content":"literal ,} text"}')
        self.assertEqual(data["content"], "literal ,} text")

    def test_parse_json_returns_none_for_invalid_json(self):
        self.assertIsNone(_parse_json("not json"))


class TestRevisionFeedbackSection(unittest.TestCase):
    def test_build_revision_feedback_section_includes_qa_and_factcheck_guidance(self):
        section = _build_revision_feedback_section(
            {
                "qa": {
                    "total": 61,
                    "threshold": 75,
                    "reason": "핵심 정리 불릿 부족",
                    "issues": ["핵심 정리 불릿 부족", "첫 문장이 기사체/상투구에 가까움"],
                    "worst_axis": "hook",
                    "regulation": 2,
                    "fact_violation": True,
                },
                "fact_check": {
                    "summary": "실패 (정확도=50%, 미검증=1, 환각=1)",
                    "issues": ["[환각 의심] 수치: '87%' - 소스에서 확인 불가"],
                    "accuracy_score": 0.5,
                    "hallucinated_claims": 1,
                },
            }
        )
        self.assertIn("재생성 보정 지시", section)
        self.assertIn("QA score/threshold: 61/75", section)
        self.assertIn("Weakest QA axis: hook", section)
        self.assertIn("Fact violation detected", section)
        self.assertIn("Regulation score is low", section)
        self.assertIn("FactCheck", section)
        self.assertIn("1", section)
        self.assertIn("환각 의심 주장 수: 1", section)


class TestFactGuardrailSection(unittest.TestCase):
    def test_build_fact_guardrail_section_lists_only_available_source_types(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA data center revenue rose after AI demand increased",
            context=MultiSourceContext(
                twitter_insight="Creators are discussing NVIDIA demand",
                news_insight="News headlines report higher data center revenue",
            ),
            trend_context=TrendContext(trigger_event="NVIDIA reported a data center revenue increase"),
        )

        section = _build_fact_guardrail_section(trend)

        self.assertIn("Source attribution requirement", section)
        self.assertIn("X reactions", section)
        self.assertIn("news headlines", section)
        self.assertIn("structured trend context", section)
        self.assertNotIn("Reddit discussion", section)


if __name__ == "__main__":
    unittest.main()
