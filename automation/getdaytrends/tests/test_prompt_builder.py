import unittest

from prompt_builder import _build_revision_feedback_section, _parse_json


class TestPromptBuilderParseJson(unittest.TestCase):
    def test_parse_json_returns_dict(self):
        data = _parse_json('{"topic":"AI","count":1}')
        self.assertEqual(data, {"topic": "AI", "count": 1})

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

        self.assertIn("[재생성 보정 지시]", section)
        self.assertIn("QA 총점/기준: 61/75", section)
        self.assertIn("가장 약한 축: hook", section)
        self.assertIn("FactCheck 요약", section)
        self.assertIn("환각 의심 주장 수: 1", section)


if __name__ == "__main__":
    unittest.main()
