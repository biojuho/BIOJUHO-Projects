"""Regression tests for entity false-positive allowlisting in the fact auditor.

The candidate-entity extractor uses a suffix heuristic (…부/원/시/…) that
mis-classifies common Korean words like 전부/일부/내부 as proper nouns, which then
trip the "컨텍스트 밖 고유명사" hallucination penalty and fail otherwise-good
tweets. These tests pin the allowlist behaviour: common words are dropped while
real organisations are still flagged when absent from the context corpus.
"""

from content_qa import _normalized_candidate_entities


class TestEntityAllowlist:
    def test_common_suffix_words_not_treated_as_entities(self):
        ents = _normalized_candidate_entities("전부 일부 내부 외부 대부분 다 모였다")
        for word in ("전부", "일부", "내부", "외부", "대부"):
            assert word not in ents, f"{word} should be allowlisted"

    def test_generic_tool_names_not_entities(self):
        ents = _normalized_candidate_entities("회사 Slack 채널에 공유했다")
        assert "slack" not in ents

    def test_real_organisation_still_extracted(self):
        # 교육부 is a real ministry — it must remain checkable (not allowlisted).
        ents = _normalized_candidate_entities("교육부가 새 정책을 발표했다")
        assert "교육부" in ents

    def test_digit_leading_quantities_not_entities(self):
        # 10만원/2시/3개월 are quantities (suffix heuristic catches 원/시), not
        # proper nouns; the numeric auditor handles them instead.
        ents = _normalized_candidate_entities("10만원에 2시부터 3개월간 진행")
        for q in ("10만원", "2시", "3개월"):
            assert q not in ents

    def test_digit_leading_filter_keeps_real_orgs(self):
        ents = _normalized_candidate_entities("서울시와 교육부가 10만원을 지원")
        assert "서울시" in ents and "교육부" in ents
