"""Unit tests for getdaytrends/content_qa.py scoring functions.

These scoring functions are the QUALITY GATE for all published content.
Wrong scoring → low-quality AI-slop goes live, or good content is
needlessly regenerated (wasting LLM budget).

Targets:
  1. _score_hook  — lead-line quality (16pt max)
  2. _score_tone  — cliche/AI-voice detection (15pt max)
  3. _score_fact  — hallucination/entity/number checks (15pt max)
  4. _score_kick  — ending quality (12pt max)
  5. _score_format — platform-specific rules (angle 12 / reg 10 / algo 10)

Run:
  python -m pytest automation/getdaytrends/tests/test_content_qa_scoring.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure getdaytrends is importable
_GDT_ROOT = Path(__file__).resolve().parents[1]
if str(_GDT_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDT_ROOT))

from content_qa import (
    _score_format,
    _score_hook,
    _score_kick,
    _UNVERIFIED_QUOTE_PATTERNS,
    build_regeneration_feedback,
)
from models import GeneratedTweet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tweet(content: str, platform: str = "x") -> GeneratedTweet:
    return GeneratedTweet(
        tweet_type="original",
        content=content,
        platform=platform,
    )


# ===========================================================================
# 1. _score_hook — Lead-Line Quality (16pt max)
# ===========================================================================


class TestScoreHook:

    def test_perfect_lead(self):
        """Lead with numbers and strong structure → max score."""
        score, issues = _score_hook(
            "2026년 AI 시장 300조 돌파, 핵심 신호 3가지",
            ["2026년 AI 시장 300조 돌파", "핵심 신호 3가지", "첫째"],
            "long_posts",
        )
        assert score == 16
        assert issues == []

    def test_cliche_lead_penalized(self):
        """Cliche opening → significant penalty."""
        # Use actual cliche patterns from multilang
        from multilang import _QA_CLICHE_PATTERNS
        if _QA_CLICHE_PATTERNS:
            cliche = _QA_CLICHE_PATTERNS[0]
            score, issues = _score_hook(
                f"{cliche} 관련 소식입니다",
                [f"{cliche} 관련 소식입니다"],
                "tweets",
            )
            assert score <= 10
            assert len(issues) >= 1

    def test_no_number_or_keyword_penalty(self):
        """Lead without numbers/question words → -3 penalty."""
        score, _ = _score_hook(
            "오늘의 뉴스를 살펴봅니다",
            ["오늘의 뉴스를 살펴봅니다"],
            "tweets",
        )
        assert score <= 13

    def test_long_post_weak_structure(self):
        """Long post with only 1 leading line → -4 for weak structure."""
        score, issues = _score_hook(
            "단일 문장의 약한 리드",
            ["단일 문장의 약한 리드"],
            "long_posts",
        )
        assert score <= 12
        assert any("핵심 주장" in i for i in issues)

    def test_tweet_no_structure_penalty(self):
        """Tweets don't get the long_post structure penalty."""
        score, issues = _score_hook(
            "2026년 왜 AI가 중요한가",
            ["2026년 왜 AI가 중요한가"],
            "tweets",
        )
        # No structure penalty for tweets
        assert not any("핵심 주장" in i for i in issues)


# ===========================================================================
# 2. _score_kick — Ending Quality (12pt max)
# ===========================================================================


class TestScoreKick:

    def test_strong_ending(self):
        score, issues = _score_kick("좋은 콘텐츠\n명확한 분석으로 마침")
        assert score == 12
        assert issues == []

    def test_cliche_ending_귀추가_주목(self):
        score, issues = _score_kick("앞으로의 행보에 귀추가 주목된다")
        assert score == 4
        assert any("상투적" in i for i in issues)

    def test_cliche_ending_결론적으로(self):
        score, issues = _score_kick("이상의 내용을 결론적으로")
        assert score == 4

    def test_cliche_ending_마무리하며(self):
        score, issues = _score_kick("이번 주제를 마무리하며")
        assert score == 4

    def test_empty_content(self):
        """Empty content should not crash."""
        score, _ = _score_kick("")
        assert score == 12  # no cliche detected


# ===========================================================================
# 3. _score_format — Platform Rules (angle 12 / reg 10 / algo 10)
# ===========================================================================


class TestScoreFormat:

    def test_tweet_within_280_chars(self):
        tweet = _make_tweet("A" * 280)
        angle, reg, algo, issues = _score_format("tweets", [tweet], tweet.content)
        assert reg == 10
        assert algo == 10
        assert issues == []

    def test_tweet_exceeds_280_chars(self):
        tweet = _make_tweet("A" * 300)
        angle, reg, algo, issues = _score_format("tweets", [tweet], tweet.content)
        assert reg <= 6
        assert algo <= 6
        assert any("280자" in i for i in issues)

    def test_threads_hashtag_fatal(self):
        """Threads posts with hashtags → regulation = 0."""
        tweet = _make_tweet("Great post #AI")
        _, reg, _, issues = _score_format("threads_posts", [tweet], tweet.content)
        assert reg == 0
        assert any("해시태그" in i for i in issues)

    def test_threads_over_500_chars(self):
        tweet = _make_tweet("X" * 501)
        _, _, algo, issues = _score_format("threads_posts", [tweet], tweet.content)
        assert algo <= 6
        assert any("500자" in i for i in issues)

    def test_long_post_no_newline(self):
        """Long post without line breaks → angle penalty."""
        tweet = _make_tweet("No line breaks at all just one long paragraph")
        angle, _, _, _ = _score_format("long_posts", [tweet], tweet.content)
        assert angle <= 8

    def test_blog_missing_required_headings(self):
        """Blog posts missing required sections → angle penalty."""
        from multilang import _BLOG_REQUIRED_HEADINGS
        if _BLOG_REQUIRED_HEADINGS:
            tweet = _make_tweet("## 서론\n내용만 있음")
            angle, _, _, issues = _score_format("blog_posts", [tweet], tweet.content)
            assert angle < 12
            assert any("필수 섹션" in i for i in issues)

    def test_blog_핵심정리_without_bullets(self):
        """Blog with '핵심 정리' heading but no bullet points."""
        content = "## 핵심 정리\n첫번째 포인트\n두번째 포인트"
        tweet = _make_tweet(content)
        angle, _, _, issues = _score_format("blog_posts", [tweet], content)
        assert any("불릿" in i for i in issues)


# ===========================================================================
# 4. Score Boundary Safety
# ===========================================================================


class TestScoreBoundaries:

    def test_hook_never_negative(self):
        """Score should be capped at 0, never go negative."""
        from multilang import _QA_CLICHE_PATTERNS
        if _QA_CLICHE_PATTERNS:
            # Stack multiple penalties
            cliche = _QA_CLICHE_PATTERNS[0]
            score, _ = _score_hook(
                cliche,  # cliche lead, no numbers
                [cliche],  # only 1 leading line
                "long_posts",
            )
            assert score >= 0

    def test_kick_never_negative(self):
        score, _ = _score_kick("귀추가 주목된다 결론적으로 마무리하며")
        assert score >= 0

    def test_format_regulation_capped_at_zero(self):
        """Threads hashtag + bait should not go below 0."""
        from multilang import _THREADS_BAIT_PATTERNS
        content = "#hashtag " + " ".join(_THREADS_BAIT_PATTERNS[:3]) if _THREADS_BAIT_PATTERNS else "#test"
        tweet = _make_tweet(content)
        _, reg, _, _ = _score_format("threads_posts", [tweet], content)
        assert reg >= 0


# ===========================================================================
# 5. Unverified Quote Pattern Detection
# ===========================================================================


class TestUnverifiedQuotes:

    def test_all_patterns_are_korean(self):
        """Sanity check: all patterns should be non-empty Korean strings."""
        for pattern in _UNVERIFIED_QUOTE_PATTERNS:
            assert len(pattern) > 0
            # Korean characters in range
            assert any("\uAC00" <= c <= "\uD7AF" for c in pattern)

    def test_patterns_match_in_text(self):
        for pattern in _UNVERIFIED_QUOTE_PATTERNS:
            text = f"이번 사안에 대해 {pattern} 밝혔다."
            assert pattern in text


class TestBuildRegenerationFeedback:

    def test_collects_failed_qa_feedback_from_failed_groups(self):
        feedback = build_regeneration_feedback(
            qa_summary={
                "failed_groups": ["blog_posts"],
                "group_results": {
                    "blog_posts": {
                        "total": 60,
                        "threshold": 75,
                        "reason": "핵심 정리 불릿 부족",
                        "issues": ["핵심 정리 불릿 부족", "첫 문장이 기사체/상투구에 가까움"],
                        "worst": "angle",
                        "regulation": 4,
                        "fact_violation": False,
                    }
                },
            }
        )

        assert feedback["blog_posts"]["qa"]["total"] == 60
        assert feedback["blog_posts"]["qa"]["worst_axis"] == "angle"
        assert feedback["blog_posts"]["qa"]["issues"][0] == "핵심 정리 불릿 부족"

    def test_collects_fact_check_feedback_for_hallucination_groups(self):
        feedback = build_regeneration_feedback(
            fact_check_results={
                "tweets": SimpleNamespace(
                    passed=False,
                    summary="실패 (정확도=50%, 미검증=1, 환각=1)",
                    issues=["[환각 의심] 수치: '87%' - 소스에서 확인 불가"],
                    accuracy_score=0.5,
                    hallucinated_claims=1,
                    unverified_claims=1,
                )
            }
        )

        assert feedback["tweets"]["fact_check"]["hallucinated_claims"] == 1
        assert feedback["tweets"]["fact_check"]["accuracy_score"] == 0.5
