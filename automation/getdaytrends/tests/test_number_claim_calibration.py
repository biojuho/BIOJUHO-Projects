"""Regression tests for casual-count exclusion in the numeric fact auditor.

The fact auditor flags numbers absent from the trend context as possible
hallucinations. Small bare Korean counts (3개, 5명) are conversational, not
load-bearing claims, and were causing false-positive fact_violations that
forced needless regeneration. These tests pin the calibration: small bare
counts are dropped, while larger numbers, magnitude units (만/억/조), currency,
and percentages stay checked.
"""

from content_qa import (
    _is_small_casual_count,
    _normalized_number_claims,
    _unknown_number_fact_penalty,
)


class TestSmallCasualCount:
    def test_one_and_two_digit_bare_counts_excluded(self):
        for claim in ("3개", "5명", "12건", "99개"):
            assert _is_small_casual_count(claim) is True

    def test_large_and_magnitude_numbers_kept(self):
        for claim in ("300명", "100개", "10억원", "5만명", "1,000개"):
            assert _is_small_casual_count(claim) is False


class TestNormalizedNumberClaims:
    def test_excludes_small_counts_keeps_real_stats(self):
        claims = _normalized_number_claims("반응 3개 달렸고 300명이 모였다. 10억원 투자. 5만명 참여.")
        assert "3개" not in claims
        assert "300명" in claims
        assert "10억원" in claims
        assert "5만명" in claims

    def test_casual_count_not_flagged_as_unsupported(self):
        # "반응 3개" appears only in the generated text, not the corpus, but a
        # small casual count must not trip the unsupported-number penalty.
        penalty, msg = _unknown_number_fact_penalty("댓글 반응 3개 달림", allowed_corpus="")
        assert penalty == 0
        assert msg == ""

    def test_real_unsupported_stat_still_flagged(self):
        penalty, msg = _unknown_number_fact_penalty("매출 300억원 증가", allowed_corpus="")
        assert penalty > 0
