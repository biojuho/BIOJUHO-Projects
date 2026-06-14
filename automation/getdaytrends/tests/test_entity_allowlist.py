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
