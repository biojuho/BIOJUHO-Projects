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

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure getdaytrends is importable
_GDT_ROOT = Path(__file__).resolve().parents[1]
if str(_GDT_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDT_ROOT))

import content_qa
from config import AppConfig
from content_qa import (
    _UNVERIFIED_QUOTE_PATTERNS,
    _score_fact,
    _score_format,
    _score_hook,
    _score_kick,
    _score_tone,
    build_regeneration_feedback,
    regenerate_content_groups,
)
from models import GeneratedTweet, ScoredTrend, TweetBatch

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
    def test_tweet_within_shortform_range(self):
        """[shortform-only] 160~240자 범위 내 트윗은 페널티 없음."""
        tweet = _make_tweet("A" * 200)
        angle, reg, algo, issues = _score_format("tweets", [tweet], tweet.content)
        assert reg == 10
        assert algo == 10
        assert issues == []

    def test_tweet_exceeds_240_chars(self):
        """[shortform-only] 240자 초과 시 regulation/algorithm 감점."""
        tweet = _make_tweet("A" * 260)
        _, reg, algo, issues = _score_format("tweets", [tweet], tweet.content)
        assert reg <= 6
        assert algo <= 6
        assert any("240자" in i for i in issues)

    def test_tweet_under_160_chars(self):
        """[shortform-only] 160자 미만 시 angle 감점 (정보 밀도 부족)."""
        tweet = _make_tweet("A" * 100)
        angle, _, algo, issues = _score_format("tweets", [tweet], tweet.content)
        assert angle < 12
        assert any("160자 미만" in i for i in issues)

    def test_repeated_tweet_type_variants_penalized(self):
        tweets = [
            GeneratedTweet(tweet_type="analysis", content="A" * 180),
            GeneratedTweet(tweet_type=" analysis ", content="B" * 180),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("repeated tweet_type variant" in i for i in issues)
        assert not any("duplicate generated draft" in i for i in issues)

    def test_repeated_tweet_type_separator_variants_penalized(self):
        tweets = [
            GeneratedTweet(tweet_type="분석형", content="A" * 180),
            GeneratedTweet(tweet_type="분석 형!", content="B" * 180),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("repeated tweet_type variant" in i for i in issues)
        assert not any("duplicate generated draft" in i for i in issues)

    def test_missing_tweet_type_variants_penalized(self):
        tweets = [
            GeneratedTweet(tweet_type="", content="A" * 180),
            GeneratedTweet(tweet_type="question", content="B" * 180),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("missing tweet_type variant" in i for i in issues)
        assert not any("repeated tweet_type variant" in i for i in issues)

    def test_punctuation_only_tweet_type_variants_count_as_missing(self):
        tweets = [
            GeneratedTweet(tweet_type=" - ", content="A" * 180),
            GeneratedTweet(tweet_type="question", content="B" * 180),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("missing tweet_type variant" in i for i in issues)
        assert not any("repeated tweet_type variant" in i for i in issues)

    def test_duplicate_tweet_drafts_penalized(self):
        content = ("Duplicated content with enough context. " * 5).strip()
        tweets = [_make_tweet(content), _make_tweet(f"  {content}\n")]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 9
        assert algo <= 8
        assert any("duplicate generated draft" in i for i in issues)

    def test_decorated_duplicate_tweet_drafts_penalized(self):
        content = (
            "AI demand is lifting cloud budgets while chip supply remains tight. "
            "Operators need margin, latency, and capex checks before chasing the rally. "
            "That makes procurement discipline the real signal."
        )
        tweets = [
            GeneratedTweet(tweet_type="analysis", content=f"1) {content}! https://a.example/x #AI"),
            GeneratedTweet(tweet_type="counterpoint", content=f"2. {content}... https://b.example/y #Cloud"),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 9
        assert algo <= 8
        assert any("duplicate generated draft" in i for i in issues)

    def test_distinct_tweet_drafts_with_shared_decoration_not_duplicate(self):
        first = (
            "AI demand is lifting cloud budgets while chip supply remains tight. "
            "Operators need margin, latency, and capex checks before chasing the rally. "
            "That makes procurement discipline the real signal."
        )
        second = (
            "AI app demand is changing where teams spend first. "
            "Inference costs, product retention, and data access now matter more than raw model hype. "
            "That shifts the signal toward execution quality."
        )
        tweets = [
            GeneratedTweet(tweet_type="analysis", content=f"1) {first}! https://a.example/x #AI"),
            GeneratedTweet(tweet_type="counterpoint", content=f"2. {second}... https://b.example/y #Cloud"),
        ]

        _, reg, _, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert not any("duplicate generated draft" in i for i in issues)

    def test_repeated_opening_hook_tweet_drafts_penalized(self):
        tweets = [
            GeneratedTweet(
                tweet_type="analysis",
                content=(
                    "AI demand is the real stress test.\n"
                    "Cloud budgets are rising, but operators still need margin checks before adding GPU capacity. "
                    "The practical signal is whether inference demand can pay for the next capex cycle."
                ),
            ),
            GeneratedTweet(
                tweet_type="counterpoint",
                content=(
                    "AI demand is the real stress test.\n"
                    "Chip buyers are racing for supply, but procurement teams still need latency, energy, and utilization proof. "
                    "The risk is treating shortage noise as durable demand."
                ),
            ),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("repeated opening hook" in i for i in issues)
        assert not any("duplicate generated draft" in i for i in issues)

    def test_distinct_opening_hook_tweet_drafts_not_penalized(self):
        tweets = [
            GeneratedTweet(
                tweet_type="analysis",
                content=(
                    "AI demand is the real stress test.\n"
                    "Cloud budgets are rising, but operators still need margin checks before adding GPU capacity. "
                    "The practical signal is whether inference demand can pay for the next capex cycle."
                ),
            ),
            GeneratedTweet(
                tweet_type="counterpoint",
                content=(
                    "Chip supply is not the only bottleneck.\n"
                    "Procurement teams also need latency, energy, and utilization proof before treating shortage noise as durable demand. "
                    "That makes execution quality the cleaner signal."
                ),
            ),
        ]

        _, reg, _, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert not any("repeated opening hook" in i for i in issues)

    def test_repeated_closing_kick_tweet_drafts_penalized(self):
        tweets = [
            GeneratedTweet(
                tweet_type="analysis",
                content=(
                    "AI demand is the real stress test.\n"
                    "Cloud budgets are rising, but operators still need margin checks before adding GPU capacity. "
                    "That makes execution quality the cleaner signal."
                ),
            ),
            GeneratedTweet(
                tweet_type="counterpoint",
                content=(
                    "Chip supply is not the only bottleneck.\n"
                    "Procurement teams also need latency, energy, and utilization proof before treating shortage noise as durable demand. "
                    "That makes execution quality the cleaner signal."
                ),
            ),
        ]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 10
        assert algo <= 8
        assert any("repeated closing kick" in i for i in issues)
        assert not any("duplicate generated draft" in i for i in issues)
        assert not any("repeated opening hook" in i for i in issues)

    def test_distinct_closing_kick_tweet_drafts_not_penalized(self):
        tweets = [
            GeneratedTweet(
                tweet_type="analysis",
                content=(
                    "AI demand is the real stress test.\n"
                    "Cloud budgets are rising, but operators still need margin checks before adding GPU capacity. "
                    "That makes execution quality the cleaner signal."
                ),
            ),
            GeneratedTweet(
                tweet_type="counterpoint",
                content=(
                    "Chip supply is not the only bottleneck.\n"
                    "Procurement teams also need latency, energy, and utilization proof before treating shortage noise as durable demand. "
                    "That keeps utilization proof ahead of shortage noise."
                ),
            ),
        ]

        _, reg, _, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert not any("repeated closing kick" in i for i in issues)

    def test_korean_particle_spacing_duplicate_tweet_drafts_penalized(self):
        first = "NVIDIA 수요가 다시 늘었다. 기업은 GPU를 더 산다. 데이터센터 투자가 핵심이다. " * 2
        second = "NVIDIA 수요 는 다시 늘었다. 기업 은 GPU 를 더 산다. 데이터센터 투자 가 핵심이다. " * 2
        tweets = [_make_tweet(first.strip()), _make_tweet(second.strip())]

        angle, reg, algo, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert angle <= 9
        assert algo <= 8
        assert any("duplicate generated draft" in i for i in issues)

    def test_distinct_korean_tweet_drafts_not_duplicate_after_particle_normalization(self):
        first = "NVIDIA 수요가 다시 늘었다. 기업은 GPU를 더 산다. 데이터센터 투자가 핵심이다. " * 2
        second = "NVIDIA 공급망이 다시 좁아졌다. 기업은 전력 계약을 먼저 본다. 비용 관리가 핵심이다. " * 2
        tweets = [_make_tweet(first.strip()), _make_tweet(second.strip())]

        _, reg, _, issues = _score_format("tweets", tweets, "\n".join(t.content for t in tweets))

        assert reg == 10
        assert not any("duplicate generated draft" in i for i in issues)

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


class TestScoreFact:
    def test_grounded_entity_and_percentage_pass(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA revenue rose 20% on data center demand")

        score, violation, issues = _score_fact("NVIDIA revenue rose 20% after data center demand increased", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_entity_and_percentage_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA revenue rose 20% on data center demand")

        score, violation, issues = _score_fact("OpenAI revenue rose 99% after NVIDIA demand increased", trend)

        assert score < 15
        assert violation is True
        assert any("고유명사" in issue for issue in issues)
        assert any("수치" in issue for issue in issues)

    def test_grounded_korean_percentage_word_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 12퍼센트 증가")

        score, violation, issues = _score_fact("NVIDIA 수요가 12프로 증가", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_percentage_word_claim_penalized_without_numeric_duplicate(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("NVIDIA 수요가 12프로 증가했다", trend)

        assert score < 15
        assert violation is True
        assert any("수치" in issue for issue in issues)
        assert not any("unsupported numeric claim" in issue for issue in issues)


class TestScoreFactNumericClaims:
    def test_grounded_numeric_claim_with_unit_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA invested $10 billion in data center chips")

        score, violation, issues = _score_fact("NVIDIA invested $10 billion in data center chips", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_numeric_claim_with_unit_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA expanded data center capacity")

        score, violation, issues = _score_fact("NVIDIA announced a $99 billion data center expansion", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported numeric claim" in issue for issue in issues)

    def test_grounded_bare_large_number_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA backlog reached 125000 in June")

        score, violation, issues = _score_fact("NVIDIA backlog reached 125000 in June", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_bare_large_number_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA expanded data center capacity")

        score, violation, issues = _score_fact("NVIDIA backlog reached 125000 after demand increased", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported numeric claim" in issue for issue in issues)

    def test_ungrounded_currency_amount_without_unit_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA expanded data center capacity")

        score, violation, issues = _score_fact("NVIDIA disclosed $1,000,000 for new capacity", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported numeric claim" in issue for issue in issues)

    def test_grounded_korean_numeric_claim_with_unit_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 125만명으로 증가")

        score, violation, issues = _score_fact("NVIDIA 수요가 125만 명으로 증가", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_numeric_claim_with_unit_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("NVIDIA 수요가 125만 명으로 증가했다", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported numeric claim" in issue for issue in issues)


class TestScoreFactDateClaims:
    def test_grounded_explicit_date_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA event moved to June 12 after demand shifted")

        score, violation, issues = _score_fact("NVIDIA event moved to June 12 after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_explicit_date_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("NVIDIA event moved to June 12 after demand increased", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported date claim" in issue for issue in issues)

    def test_grounded_korean_explicit_date_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 행사가 6월 12일로 이동")

        score, violation, issues = _score_fact("NVIDIA 행사가 6월 12일로 이동", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_explicit_date_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("NVIDIA 행사가 6월 12일로 이동했다", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported date claim" in issue for issue in issues)


class TestScoreFactStrongClaims:
    def test_grounded_record_high_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA hit a record high after demand rose")

        score, violation, issues = _score_fact("NVIDIA hit a record high after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_best_period_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA posted its best quarter after demand rose")

        score, violation, issues = _score_fact("NVIDIA posted its best quarter after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_rank_market_position_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA became the most valuable chipmaker after demand rose",
        )

        score, violation, issues = _score_fact(
            "NVIDIA became the most valuable chipmaker after demand rose",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_future_outcome_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA will dominate AI chips after demand rose")

        score, violation, issues = _score_fact("NVIDIA will dominate AI chips after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_competitive_comparison_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA beat expectations after demand rose")

        score, violation, issues = _score_fact("NVIDIA beat expectations after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_causal_market_reaction_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA sparked a rally after demand rose")

        score, violation, issues = _score_fact("NVIDIA sparked a rally after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_qualitative_turning_point_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA marks a turning point after demand rose")

        score, violation, issues = _score_fact("NVIDIA marks a turning point after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_online_reaction_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA sparked online debate after demand rose")

        score, violation, issues = _score_fact("NVIDIA sparked online debate after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_viral_spread_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA went viral after demand rose")

        score, violation, issues = _score_fact("NVIDIA went viral after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_conclusive_validation_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA proved AI demand is real after demand rose")

        score, violation, issues = _score_fact("NVIDIA proved AI demand is real after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_investment_certainty_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA is inevitable after demand rose")

        score, violation, issues = _score_fact("NVIDIA is inevitable after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_buy_signal_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA flashed a buy signal after demand rose")

        score, violation, issues = _score_fact("NVIDIA flashed a buy signal after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_valuation_verdict_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA is undervalued after demand rose")

        score, violation, issues = _score_fact("NVIDIA is undervalued after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_analyst_rating_action_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA was upgraded after demand rose")

        score, violation, issues = _score_fact("NVIDIA was upgraded after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_credit_rating_debt_financing_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA issued bonds after demand rose")

        score, violation, issues = _score_fact("NVIDIA issued bonds after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_earnings_guidance_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA beat earnings estimates after demand rose")

        score, violation, issues = _score_fact("NVIDIA beat earnings estimates after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_ai_benchmark_performance_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA topped the AI benchmark leaderboard after demand rose",
        )

        score, violation, issues = _score_fact("NVIDIA topped the AI benchmark leaderboard after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_financial_performance_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA revenue doubled after demand rose")

        score, violation, issues = _score_fact("NVIDIA revenue doubled after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_monetization_unit_economics_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA average revenue per user rose after demand shifted",
        )

        score, violation, issues = _score_fact("NVIDIA average revenue per user rose after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_retail_ecommerce_metric_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA average order value increased after demand rose",
        )

        score, violation, issues = _score_fact("NVIDIA average order value increased after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_budget_spending_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA capex doubled after demand shifted")

        score, violation, issues = _score_fact("NVIDIA capex doubled after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_supply_cost_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA component costs rose after demand shifted")

        score, violation, issues = _score_fact("NVIDIA component costs rose after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_accounting_charge_metric_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA recorded an impairment charge after demand shifted",
        )

        score, violation, issues = _score_fact(
            "NVIDIA recorded an impairment charge after demand shifted",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_financial_condition_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA cash balance fell after demand shifted")

        score, violation, issues = _score_fact("NVIDIA cash balance fell after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_working_capital_efficiency_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA cash conversion cycle shortened after demand shifted")

        score, violation, issues = _score_fact("NVIDIA cash conversion cycle shortened after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_subscription_pricing_billing_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA raised subscription prices after demand shifted")

        score, violation, issues = _score_fact("NVIDIA raised subscription prices after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_pricing_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA average selling price increased after demand shifted")

        score, violation, issues = _score_fact("NVIDIA average selling price increased after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_product_retention_paid_conversion_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA retention improved after demand shifted")

        score, violation, issues = _score_fact("NVIDIA retention improved after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_ad_performance_metric_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA return on ad spend rose after demand shifted",
        )

        score, violation, issues = _score_fact("NVIDIA return on ad spend rose after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_growth_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA gained market share after demand rose")

        score, violation, issues = _score_fact("NVIDIA gained market share after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_adoption_penetration_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA installed base increased after demand rose")

        score, violation, issues = _score_fact("NVIDIA installed base increased after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_web_seo_analytics_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA organic traffic increased after demand rose")

        score, violation, issues = _score_fact("NVIDIA organic traffic increased after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_developer_ecosystem_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA contributors grew after demand rose")

        score, violation, issues = _score_fact("NVIDIA contributors grew after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_ratings_awards_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA won an industry award after demand rose")

        score, violation, issues = _score_fact("NVIDIA won an industry award after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_supply_chain_customs_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA shipments were seized by customs")

        score, violation, issues = _score_fact("NVIDIA shipments were seized by customs", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_logistics_service_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA fill rate improved after demand rose")

        score, violation, issues = _score_fact("NVIDIA fill rate improved after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_operational_footprint_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA opened new stores after demand rose")

        score, violation, issues = _score_fact("NVIDIA opened new stores after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_business_outcome_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA secured a major deal after demand rose")

        score, violation, issues = _score_fact("NVIDIA secured a major deal after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_commercial_pipeline_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA bookings doubled after demand rose")

        score, violation, issues = _score_fact("NVIDIA bookings doubled after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_commercial_agreement_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA entered a joint venture after demand rose")

        score, violation, issues = _score_fact("NVIDIA entered a joint venture after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_customer_deployment_adoption_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA secured enterprise adoption after demand rose",
        )

        score, violation, issues = _score_fact("NVIDIA secured enterprise adoption after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_executive_leadership_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA appointed a new chief executive after demand rose",
        )

        score, violation, issues = _score_fact("NVIDIA appointed a new chief executive after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_security_privacy_outage_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA suffered a data breach after demand rose")

        score, violation, issues = _score_fact("NVIDIA suffered a data breach after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_security_compliance_certification_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA passed a security audit after demand rose")

        score, violation, issues = _score_fact("NVIDIA passed a security audit after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_cybersecurity_privacy_detail_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA disclosed a data breach after demand rose")

        score, violation, issues = _score_fact("NVIDIA disclosed a data breach after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_consumer_service_trust_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA issued refunds after demand rose")

        score, violation, issues = _score_fact("NVIDIA issued refunds after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_customer_reliability_metric_claim_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA customer satisfaction improved after demand rose",
        )

        score, violation, issues = _score_fact("NVIDIA customer satisfaction improved after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_customer_support_operations_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA refund rate increased after demand rose")

        score, violation, issues = _score_fact("NVIDIA refund rate increased after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_insurance_compensation_liability_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA reimbursed customers after demand rose")

        score, violation, issues = _score_fact("NVIDIA reimbursed customers after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_platform_moderation_distribution_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA account was suspended after demand rose")

        score, violation, issues = _score_fact("NVIDIA account was suspended after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_corporate_transaction_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA acquired a startup after demand rose")

        score, violation, issues = _score_fact("NVIDIA acquired a startup after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_capital_markets_listing_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA went public after demand rose")

        score, violation, issues = _score_fact("NVIDIA went public after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_shareholder_capital_action_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA authorized a share repurchase after demand rose")

        score, violation, issues = _score_fact("NVIDIA authorized a share repurchase after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_government_defense_procurement_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA secured a defense contract after demand rose")

        score, violation, issues = _score_fact("NVIDIA secured a defense contract after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_product_launch_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA launched a new chip after demand rose")

        score, violation, issues = _score_fact("NVIDIA launched a new chip after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_supply_availability_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA lead times doubled after demand rose")

        score, violation, issues = _score_fact("NVIDIA lead times doubled after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_workforce_operations_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA announced layoffs after demand shifted")

        score, violation, issues = _score_fact("NVIDIA announced layoffs after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_workforce_metric_movement_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA headcount grew after demand shifted")

        score, violation, issues = _score_fact("NVIDIA headcount grew after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_workforce_labor_extension_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA laid off employees after demand shifted")

        score, violation, issues = _score_fact("NVIDIA laid off employees after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_manufacturing_quality_metric_claim_passes(self):
        trend = ScoredTrend(keyword="TSMC", rank=1, top_insight="TSMC yield rate improved after demand shifted")

        score, violation, issues = _score_fact("TSMC yield rate improved after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_infrastructure_facility_capacity_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA opened a new data center after demand shifted")

        score, violation, issues = _score_fact("NVIDIA opened a new data center after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_compute_capacity_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA compute capacity doubled after demand shifted")

        score, violation, issues = _score_fact("NVIDIA compute capacity doubled after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_workplace_labor_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA workers went on strike after demand shifted")

        score, violation, issues = _score_fact("NVIDIA workers went on strike after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_regulatory_legal_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA received regulatory approval after demand rose")

        score, violation, issues = _score_fact("NVIDIA received regulatory approval after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_ongoing_legal_regulatory_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA faces a lawsuit after demand rose")

        score, violation, issues = _score_fact("NVIDIA faces a lawsuit after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_intellectual_property_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA won a patent case after demand rose")

        score, violation, issues = _score_fact("NVIDIA won a patent case after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_regulatory_enforcement_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA was fined by regulators after demand rose")

        score, violation, issues = _score_fact("NVIDIA was fined by regulators after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_trade_export_control_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA faced new trade curbs after demand rose")

        score, violation, issues = _score_fact("NVIDIA faced new trade curbs after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_criminal_misconduct_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA was charged with fraud after demand rose")

        score, violation, issues = _score_fact("NVIDIA was charged with fraud after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_passive_regulatory_legal_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA's license was approved after demand rose")

        score, violation, issues = _score_fact("NVIDIA's license was approved after demand rose", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_financial_distress_accounting_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA filed for bankruptcy after demand shifted")

        score, violation, issues = _score_fact("NVIDIA filed for bankruptcy after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_product_safety_recall_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA recalled a product after demand shifted")

        score, violation, issues = _score_fact("NVIDIA recalled a product after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_medical_clinical_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA passed a clinical trial after demand shifted")

        score, violation, issues = _score_fact("NVIDIA passed a clinical trial after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_scientific_research_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA published a peer-reviewed study")

        score, violation, issues = _score_fact("NVIDIA published a peer-reviewed study", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_environmental_industrial_incident_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA caused an oil spill after demand shifted")

        score, violation, issues = _score_fact("NVIDIA caused an oil spill after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_sustainability_esg_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA reached net zero after demand shifted")

        score, violation, issues = _score_fact("NVIDIA reached net zero after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_sustainability_metric_movement_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA water usage increased after demand shifted")

        score, violation, issues = _score_fact("NVIDIA water usage increased after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_grounded_sustainability_efficiency_metric_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA PUE improved after demand shifted")

        score, violation, issues = _score_fact("NVIDIA PUE improved after demand shifted", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_record_high_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA hit a record high after data center orders increased",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_largest_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA posted its largest order cycle after data center orders increased",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_first_to_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA became the first chip company to see demand increase after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_unprecedented_historic_never_before_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA demand reached unprecedented levels after data center orders",
            "NVIDIA demand hit a historic high after data center orders",
            "NVIDIA demand rose like never before after data center orders",
            "NVIDIA saw an all-time record after data center orders",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_best_period_new_peak_fresh_high_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA posted its best quarter after data center orders increased",
            "NVIDIA demand reached a new peak after data center orders",
            "NVIDIA demand hit a fresh high after data center orders",
            "NVIDIA is set for its best month after data center orders",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_rank_market_position_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA became the No. 1 AI chip stock after data center orders",
            "NVIDIA is now number one in AI chips after data center orders",
            "NVIDIA took the top spot after data center orders",
            "NVIDIA became the most valuable chipmaker after data center orders",
            "NVIDIA overtook rivals after data center orders increased",
            "NVIDIA moved to the top rank after data center orders",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_future_outcome_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA will dominate AI chips after data center orders",
            "NVIDIA is set to dominate AI chips after data center orders",
            "NVIDIA is poised to double after data center orders",
            "NVIDIA will reshape the AI market after data center orders",
            "NVIDIA is guaranteed to keep rising after data center orders",
            "NVIDIA demand will explode after data center orders",
            "NVIDIA could become the next trillion-dollar winner after data center orders",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_competitive_comparison_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA outpaced rivals after data center orders increased",
            "NVIDIA beat expectations after data center orders increased",
            "NVIDIA demand was stronger than competitors after data center orders",
            "NVIDIA performed better than rivals after data center orders",
            "NVIDIA left competitors behind after data center orders",
            "NVIDIA widened its lead after data center orders increased",
            "NVIDIA is more powerful than rivals after data center orders",
            "NVIDIA demand topped analyst expectations after data center orders",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_causal_market_reaction_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA sparked a rally after data center orders increased",
            "NVIDIA triggered a selloff after data center orders increased",
            "NVIDIA sent shares higher after data center orders increased",
            "NVIDIA pushed the stock up after data center orders increased",
            "NVIDIA fueled investor optimism after data center orders increased",
            "NVIDIA drove market gains after data center orders increased",
            "NVIDIA caused demand to surge after data center orders increased",
            "NVIDIA made investors rush in after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_qualitative_turning_point_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA is a game changer after data center orders increased",
            "NVIDIA marks a turning point after data center orders increased",
            "NVIDIA had a breakthrough moment after data center orders increased",
            "NVIDIA is a seismic shift after data center orders increased",
            "NVIDIA changes everything after data center orders increased",
            "NVIDIA is a massive tailwind after data center orders increased",
            "NVIDIA opened a new era after data center orders increased",
            "NVIDIA is a watershed moment after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_online_public_reaction_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "Everyone is talking about NVIDIA after data center orders increased",
            "The internet went wild over NVIDIA after data center orders increased",
            "NVIDIA sparked online debate after data center orders increased",
            "NVIDIA divided investors after data center orders increased",
            "NVIDIA became the talk of the internet after data center orders increased",
            "Social media erupted over NVIDIA after data center orders increased",
            "NVIDIA sent users into a frenzy after data center orders increased",
            "NVIDIA dominated the conversation after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_viral_spread_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA went viral after data center orders increased",
            "NVIDIA is going viral after data center orders increased",
            "NVIDIA blew up online after data center orders increased",
            "NVIDIA broke the internet after data center orders increased",
            "NVIDIA took social media by storm after data center orders increased",
            "NVIDIA caught fire online after data center orders increased",
            "NVIDIA set social media ablaze after data center orders increased",
            "NVIDIA became a meme after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_conclusive_validation_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA proved AI demand is real after data center orders increased",
            "NVIDIA confirmed the AI boom after data center orders increased",
            "NVIDIA validated the AI boom after data center orders increased",
            "NVIDIA put doubts to rest after data center orders increased",
            "NVIDIA ended the debate after data center orders increased",
            "NVIDIA settled the debate after data center orders increased",
            "NVIDIA silenced skeptics after data center orders increased",
            "NVIDIA removed uncertainty after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_investment_certainty_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA is inevitable after data center orders increased",
            "NVIDIA became a no-brainer after data center orders increased",
            "NVIDIA is a sure bet after data center orders increased",
            "NVIDIA is a safe bet after data center orders increased",
            "NVIDIA is a can't-miss trade after data center orders increased",
            "NVIDIA is a must-have for portfolios after data center orders increased",
            "NVIDIA is unstoppable after data center orders increased",
            "Investors cannot lose with NVIDIA after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_buy_market_signal_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA flashed a buy signal after data center orders increased",
            "NVIDIA gave investors a green light after data center orders increased",
            "NVIDIA gave the market an all-clear after data center orders increased",
            "NVIDIA showed it is time to buy after data center orders increased",
            "NVIDIA created a buying opportunity after data center orders increased",
            "NVIDIA offered a perfect entry point after data center orders increased",
            "Traders should load up on NVIDIA after data center orders increased",
            "Investors should double down on NVIDIA after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_valuation_verdict_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA is undervalued after data center orders increased",
            "NVIDIA is overvalued after data center orders increased",
            "NVIDIA looks cheap after data center orders increased",
            "NVIDIA looks expensive after data center orders increased",
            "NVIDIA is a bargain after data center orders increased",
            "NVIDIA has upside after data center orders increased",
            "NVIDIA has downside after data center orders increased",
            "NVIDIA price target moved higher after data center orders increased",
            "NVIDIA target price moved lower after data center orders increased",
            "NVIDIA valuation looks stretched after data center orders increased",
            "NVIDIA is priced for perfection after data center orders increased",
            "NVIDIA has room to run after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_analyst_rating_action_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA was upgraded after data center orders increased",
            "NVIDIA got downgraded after data center orders increased",
            "NVIDIA earned a buy rating after data center orders increased",
            "NVIDIA landed a sell rating after data center orders increased",
            "NVIDIA kept a hold rating after data center orders increased",
            "NVIDIA moved to outperform after data center orders increased",
            "NVIDIA moved to underperform after data center orders increased",
            "NVIDIA was cut to neutral after data center orders increased",
            "NVIDIA was raised to buy after data center orders increased",
            "NVIDIA was lowered to sell after data center orders increased",
            "NVIDIA was initiated at buy after data center orders increased",
            "Wall Street upgraded NVIDIA after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_credit_rating_debt_financing_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA credit rating was downgraded after data center orders increased",
            "NVIDIA credit rating was upgraded after data center orders increased",
            "Moody's downgraded NVIDIA after data center orders increased",
            "S&P put NVIDIA on negative watch after data center orders increased",
            "Fitch raised NVIDIA outlook after data center orders increased",
            "NVIDIA issued bonds after data center orders increased",
            "NVIDIA sold debt after data center orders increased",
            "NVIDIA secured a term loan after data center orders increased",
            "NVIDIA refinanced debt after data center orders increased",
            "NVIDIA extended its credit facility after data center orders increased",
            "NVIDIA breached debt covenants after data center orders increased",
            "NVIDIA received a covenant waiver after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_earnings_guidance_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA beat earnings estimates after data center orders increased",
            "NVIDIA missed earnings estimates after data center orders increased",
            "NVIDIA beat revenue expectations after data center orders increased",
            "NVIDIA missed revenue expectations after data center orders increased",
            "NVIDIA raised guidance after data center orders increased",
            "NVIDIA cut guidance after data center orders increased",
            "NVIDIA lifted its outlook after data center orders increased",
            "NVIDIA lowered its outlook after data center orders increased",
            "NVIDIA issued a profit warning after data center orders increased",
            "NVIDIA issued a margin warning after data center orders increased",
            "NVIDIA warned on profits after data center orders increased",
            "NVIDIA warned on margins after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_ai_benchmark_performance_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA topped the AI benchmark leaderboard after data center orders increased",
            "NVIDIA achieved state-of-the-art performance after data center orders increased",
            "NVIDIA model beat benchmark records after data center orders increased",
            "NVIDIA reduced inference latency after data center orders increased",
            "NVIDIA doubled inference throughput after data center orders increased",
            "NVIDIA cut training costs after data center orders increased",
            "NVIDIA lowered token costs after data center orders increased",
            "NVIDIA improved energy efficiency after data center orders increased",
            "NVIDIA posted the best benchmark accuracy after data center orders increased",
            "NVIDIA passed a safety evaluation after data center orders increased",
            "NVIDIA lowered hallucination rates after data center orders increased",
            "NVIDIA delivered a major speedup after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_financial_performance_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA revenue doubled after data center orders increased",
            "NVIDIA profit surged after data center orders increased",
            "NVIDIA margins expanded after data center orders increased",
            "NVIDIA gross margin hit 75% after data center orders increased",
            "NVIDIA free cash flow turned positive after data center orders increased",
            "NVIDIA returned to profitability after data center orders increased",
            "NVIDIA reported record revenue after data center orders increased",
            "NVIDIA sales crossed $10 billion after data center orders increased",
            "NVIDIA EBITDA improved after data center orders increased",
            "NVIDIA operating income jumped after data center orders increased",
            "NVIDIA backlog reached $5 billion after data center orders increased",
            "NVIDIA orders doubled after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_monetization_unit_economics_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA ARPU increased after data center orders increased",
            "NVIDIA average revenue per user rose after data center orders increased",
            "NVIDIA MRR doubled after data center orders increased",
            "NVIDIA monthly recurring revenue increased after data center orders increased",
            "NVIDIA ARR crossed $1 billion after data center orders increased",
            "NVIDIA annual recurring revenue rose after data center orders increased",
            "NVIDIA GMV rose after data center orders increased",
            "NVIDIA gross merchandise value increased after data center orders increased",
            "NVIDIA take rate improved after data center orders increased",
            "NVIDIA LTV/CAC improved after data center orders increased",
            "NVIDIA customer acquisition cost fell after data center orders increased",
            "NVIDIA unit economics turned positive after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_retail_ecommerce_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA AOV rose after data center orders increased",
            "NVIDIA average order value increased after data center orders increased",
            "NVIDIA basket size fell after data center orders increased",
            "NVIDIA average basket size increased after data center orders increased",
            "NVIDIA cart abandonment rate fell after data center orders increased",
            "NVIDIA checkout conversion improved after data center orders increased",
            "NVIDIA same-store sales increased after data center orders increased",
            "NVIDIA same store sales fell after data center orders increased",
            "NVIDIA comp sales rose after data center orders increased",
            "NVIDIA comparable sales declined after data center orders increased",
            "NVIDIA store traffic increased after data center orders increased",
            "NVIDIA foot traffic rose after data center orders increased",
            "NVIDIA sell-through rate improved after data center orders increased",
            "NVIDIA channel sell through declined after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_budget_spending_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA capex doubled after data center orders increased",
            "NVIDIA capital expenditure rose after data center orders increased",
            "NVIDIA capital spending increased after data center orders increased",
            "NVIDIA infrastructure spending surged after data center orders increased",
            "NVIDIA cloud spend increased after data center orders increased",
            "NVIDIA AI infrastructure spend doubled after data center orders increased",
            "NVIDIA R&D spending rose after data center orders increased",
            "NVIDIA research and development spending increased after data center orders increased",
            "NVIDIA marketing budget increased after data center orders increased",
            "NVIDIA procurement budget doubled after data center orders increased",
            "NVIDIA data center budget rose after data center orders increased",
            "NVIDIA investment budget increased after data center orders increased",
            "NVIDIA opex fell after data center orders increased",
            "NVIDIA operating expenses increased after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_supply_cost_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA component costs rose after data center orders increased",
            "NVIDIA component cost fell after data center orders increased",
            "NVIDIA raw material costs increased after data center orders increased",
            "NVIDIA input costs declined after data center orders increased",
            "NVIDIA freight costs surged after data center orders increased",
            "NVIDIA shipping costs fell after data center orders increased",
            "NVIDIA logistics costs increased after data center orders increased",
            "NVIDIA energy costs rose after data center orders increased",
            "NVIDIA wafer prices increased after data center orders increased",
            "NVIDIA memory prices fell after data center orders increased",
            "NVIDIA packaging costs rose after data center orders increased",
            "NVIDIA bill of materials cost increased after data center orders increased",
            "NVIDIA BOM cost fell after data center orders increased",
            "NVIDIA COGS declined after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_accounting_charge_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA recorded an impairment charge after data center orders increased",
            "NVIDIA took a goodwill impairment after data center orders increased",
            "NVIDIA wrote down inventory after data center orders increased",
            "NVIDIA wrote off obsolete inventory after data center orders increased",
            "NVIDIA booked a restructuring charge after data center orders increased",
            "NVIDIA recorded a warranty charge after data center orders increased",
            "NVIDIA increased inventory reserves after data center orders increased",
            "NVIDIA took a one-time charge after data center orders increased",
            "NVIDIA recorded a non-cash charge after data center orders increased",
            "NVIDIA asset impairment rose after data center orders increased",
            "NVIDIA inventory write-down increased after data center orders increased",
            "NVIDIA tax expense increased after data center orders increased",
            "NVIDIA effective tax rate fell after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_financial_condition_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA cash balance fell after data center orders increased",
            "NVIDIA cash reserves increased after data center orders increased",
            "NVIDIA net debt rose after data center orders increased",
            "NVIDIA debt load increased after data center orders increased",
            "NVIDIA leverage fell after data center orders increased",
            "NVIDIA cash burn increased after data center orders increased",
            "NVIDIA burn rate declined after data center orders increased",
            "NVIDIA cash runway extended after data center orders increased",
            "NVIDIA runway shortened after data center orders increased",
            "NVIDIA liquidity improved after data center orders increased",
            "NVIDIA working capital fell after data center orders increased",
            "NVIDIA current ratio improved after data center orders increased",
            "NVIDIA debt-to-equity ratio rose after data center orders increased",
            "NVIDIA debt to EBITDA fell after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_working_capital_efficiency_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA inventory turnover improved after data center orders increased",
            "NVIDIA inventory turnover fell after data center orders increased",
            "NVIDIA receivables turnover rose after data center orders increased",
            "NVIDIA payables turnover declined after data center orders increased",
            "NVIDIA cash conversion cycle shortened after data center orders increased",
            "NVIDIA cash conversion cycle lengthened after data center orders increased",
            "NVIDIA working capital cycle improved after data center orders increased",
            "NVIDIA DSO fell after data center orders increased",
            "NVIDIA DPO increased after data center orders increased",
            "NVIDIA days sales outstanding rose after data center orders increased",
            "NVIDIA days payable outstanding fell after data center orders increased",
            "NVIDIA days inventory outstanding increased after data center orders increased",
            "NVIDIA inventory days dropped after data center orders increased",
            "NVIDIA receivable days improved after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_subscription_pricing_billing_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA raised subscription prices after data center orders increased",
            "NVIDIA cut subscription prices after data center orders increased",
            "NVIDIA subscription pricing increased after data center orders increased",
            "NVIDIA monthly fees rose after data center orders increased",
            "NVIDIA annual plan prices increased after data center orders increased",
            "NVIDIA seat prices doubled after data center orders increased",
            "NVIDIA usage-based pricing launched after data center orders increased",
            "NVIDIA launched a paid tier after data center orders increased",
            "NVIDIA removed the free plan after data center orders increased",
            "NVIDIA introduced metered billing after data center orders increased",
            "NVIDIA raised platform fees after data center orders increased",
            "NVIDIA lowered platform fees after data center orders increased",
            "NVIDIA commission rate increased after data center orders increased",
            "NVIDIA discounting declined after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_pricing_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA ASP rose after data center orders increased",
            "NVIDIA ASP declined after data center orders increased",
            "NVIDIA average selling price increased after data center orders increased",
            "NVIDIA average selling prices fell after data center orders increased",
            "NVIDIA unit price increased after data center orders increased",
            "NVIDIA selling prices rose after data center orders increased",
            "NVIDIA list prices fell after data center orders increased",
            "NVIDIA wholesale prices increased after data center orders increased",
            "NVIDIA resale prices spiked after data center orders increased",
            "NVIDIA discount rate fell after data center orders increased",
            "NVIDIA discount rates increased after data center orders increased",
            "NVIDIA rebates increased after data center orders increased",
            "NVIDIA price premium widened after data center orders increased",
            "NVIDIA price gap narrowed after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_ad_performance_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA ROAS improved after data center orders increased",
            "NVIDIA return on ad spend rose after data center orders increased",
            "NVIDIA CTR increased after data center orders increased",
            "NVIDIA click-through rate improved after data center orders increased",
            "NVIDIA CPC fell after data center orders increased",
            "NVIDIA cost per click dropped after data center orders increased",
            "NVIDIA CPM declined after data center orders increased",
            "NVIDIA cost per mille fell after data center orders increased",
            "NVIDIA ad revenue increased after data center orders increased",
            "NVIDIA advertising revenue doubled after data center orders increased",
            "NVIDIA ad spend fell after data center orders increased",
            "NVIDIA campaign impressions surged after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_web_seo_analytics_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA organic traffic increased after data center orders increased",
            "NVIDIA website traffic doubled after data center orders increased",
            "NVIDIA web traffic rose after data center orders increased",
            "NVIDIA page views surged after data center orders increased",
            "NVIDIA unique visitors increased after data center orders increased",
            "NVIDIA bounce rate fell after data center orders increased",
            "NVIDIA average session duration rose after data center orders increased",
            "NVIDIA search ranking improved after data center orders increased",
            "NVIDIA SEO ranking improved after data center orders increased",
            "NVIDIA domain authority increased after data center orders increased",
            "NVIDIA referral traffic rose after data center orders increased",
            "NVIDIA newsletter signups doubled after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_developer_ecosystem_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA GitHub stars doubled after data center orders increased",
            "NVIDIA GitHub forks increased after data center orders increased",
            "NVIDIA repository stars crossed 10000 after data center orders increased",
            "NVIDIA contributors grew after data center orders increased",
            "NVIDIA external contributors doubled after data center orders increased",
            "NVIDIA pull requests increased after data center orders increased",
            "NVIDIA API calls doubled after data center orders increased",
            "NVIDIA API usage increased after data center orders increased",
            "NVIDIA SDK adoption increased after data center orders increased",
            "NVIDIA developer signups doubled after data center orders increased",
            "NVIDIA Docker pulls rose after data center orders increased",
            "NVIDIA container pulls increased after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_growth_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA gained market share after data center orders increased",
            "NVIDIA lost market share after data center orders increased",
            "NVIDIA market share doubled after data center orders increased",
            "NVIDIA downloads surged after data center orders increased",
            "NVIDIA crossed one million downloads after data center orders increased",
            "NVIDIA monthly active users rose after data center orders increased",
            "NVIDIA daily active users fell after data center orders increased",
            "NVIDIA subscribers doubled after data center orders increased",
            "NVIDIA reached one million subscribers after data center orders increased",
            "NVIDIA conversion rate improved after data center orders increased",
            "NVIDIA engagement rate hit a record after data center orders increased",
            "NVIDIA app installs spiked after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_adoption_penetration_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA install base grew after data center orders increased",
            "NVIDIA installed base increased after data center orders increased",
            "NVIDIA customer base doubled after data center orders increased",
            "NVIDIA user base grew after data center orders increased",
            "NVIDIA attach rate improved after data center orders increased",
            "NVIDIA attach rates rose after data center orders increased",
            "NVIDIA market penetration increased after data center orders increased",
            "NVIDIA category penetration rose after data center orders increased",
            "NVIDIA household penetration fell after data center orders increased",
            "NVIDIA enterprise penetration improved after data center orders increased",
            "NVIDIA share of wallet increased after data center orders increased",
            "NVIDIA wallet share rose after data center orders increased",
            "NVIDIA category share increased after data center orders increased",
            "NVIDIA segment share rose after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_ratings_awards_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA won an industry award after data center orders increased",
            "NVIDIA received an innovation award after data center orders increased",
            "NVIDIA was named product of the year after data center orders increased",
            "NVIDIA earned editor's choice after data center orders increased",
            "NVIDIA earned a five-star rating after data center orders increased",
            "NVIDIA app rating rose after data center orders increased",
            "NVIDIA reviews improved after data center orders increased",
            "NVIDIA reached 4.9 stars after data center orders increased",
            "NVIDIA topped the App Store rankings after data center orders increased",
            "NVIDIA became the top-rated app after data center orders increased",
            "NVIDIA Trustpilot score improved after data center orders increased",
            "NVIDIA G2 rating increased after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_supply_chain_customs_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA shipments were seized by customs after data center orders increased",
            "Customs seized NVIDIA chips after data center orders increased",
            "NVIDIA shipments were blocked at customs after data center orders increased",
            "NVIDIA cargo was detained at the port after data center orders increased",
            "NVIDIA supplier strike disrupted production after data center orders increased",
            "NVIDIA port delays halted deliveries after data center orders increased",
            "NVIDIA supply chain collapsed after data center orders increased",
            "NVIDIA inventory stockout hit customers after data center orders increased",
            "NVIDIA component shortage forced production cuts after data center orders increased",
            "NVIDIA import ban blocked chips after data center orders increased",
            "NVIDIA smuggling network shipped chips after data center orders increased",
            "NVIDIA gray-market shipments surged after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_logistics_service_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA fill rate improved after data center orders increased",
            "NVIDIA order fill rate fell after data center orders increased",
            "NVIDIA on-time delivery improved after data center orders increased",
            "NVIDIA on time delivery fell after data center orders increased",
            "NVIDIA OTIF rose after data center orders increased",
            "NVIDIA delivery performance improved after data center orders increased",
            "NVIDIA late deliveries increased after data center orders increased",
            "NVIDIA shipping delays increased after data center orders increased",
            "NVIDIA freight delays declined after data center orders increased",
            "NVIDIA order fulfillment improved after data center orders increased",
            "NVIDIA fulfillment rate fell after data center orders increased",
            "NVIDIA stockouts increased after data center orders increased",
            "NVIDIA stock-outs rose after data center orders increased",
            "NVIDIA backorders rose after data center orders increased",
            "NVIDIA service levels improved after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_business_outcome_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA signed a major partnership after data center orders increased",
            "NVIDIA announced a new partnership after data center orders increased",
            "NVIDIA partnered with a top cloud provider after data center orders increased",
            "NVIDIA secured a major deal after data center orders increased",
            "NVIDIA landed a new contract after data center orders increased",
            "NVIDIA won a major order after data center orders increased",
            "NVIDIA secured a new customer after data center orders increased",
            "NVIDIA added a marquee customer after data center orders increased",
            "NVIDIA locked in a supply agreement after data center orders increased",
            "NVIDIA inked a strategic alliance after data center orders increased",
            "NVIDIA expanded its customer base after data center orders increased",
            "NVIDIA captured a major account after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_commercial_pipeline_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA signed a new enterprise customer after data center orders increased",
            "NVIDIA bookings doubled after data center orders increased",
            "NVIDIA net bookings increased after data center orders increased",
            "NVIDIA billings rose after data center orders increased",
            "NVIDIA remaining performance obligations increased after data center orders increased",
            "NVIDIA RPO rose after data center orders increased",
            "NVIDIA preorder volume doubled after data center orders increased",
            "NVIDIA pre-order volume increased after data center orders increased",
            "NVIDIA purchase orders increased after data center orders increased",
            "NVIDIA sales pipeline grew after data center orders increased",
            "NVIDIA won an RFP after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_commercial_agreement_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA entered a joint venture after data center orders increased",
            "NVIDIA formed a joint venture after data center orders increased",
            "NVIDIA announced a collaboration after data center orders increased",
            "NVIDIA signed a data licensing agreement after data center orders increased",
            "NVIDIA entered an exclusive distribution agreement after data center orders increased",
            "NVIDIA signed a reseller agreement after data center orders increased",
            "NVIDIA became an OEM partner after data center orders increased",
            "NVIDIA licensed its technology to a partner after data center orders increased",
            "NVIDIA secured a data sharing agreement after data center orders increased",
            "NVIDIA signed a memorandum of understanding after data center orders increased",
            "NVIDIA signed an MOU after data center orders increased",
            "NVIDIA became an exclusive supplier after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_customer_deployment_adoption_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA chips were adopted by a major cloud provider after data center orders increased",
            "A hyperscaler deployed NVIDIA chips after data center orders increased",
            "NVIDIA became the default supplier after data center orders increased",
            "NVIDIA won a production deployment after data center orders increased",
            "NVIDIA moved from pilot to production after data center orders increased",
            "NVIDIA completed a customer rollout after data center orders increased",
            "NVIDIA entered commercial deployment after data center orders increased",
            "NVIDIA was installed in enterprise data centers after data center orders increased",
            "NVIDIA qualified as a preferred supplier after data center orders increased",
            "NVIDIA integrated with a hyperscaler platform after data center orders increased",
            "NVIDIA passed customer acceptance testing after data center orders increased",
            "NVIDIA secured enterprise adoption after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_government_defense_procurement_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA won a Pentagon contract after data center orders increased",
            "NVIDIA secured a defense contract after data center orders increased",
            "NVIDIA received a federal grant after data center orders increased",
            "NVIDIA was selected for a government program after data center orders increased",
            "NVIDIA joined a national security project after data center orders increased",
            "NVIDIA landed a military AI deal after data center orders increased",
            "NVIDIA signed a DoD agreement after data center orders increased",
            "NVIDIA received government funding after data center orders increased",
            "NVIDIA won a public-sector tender after data center orders increased",
            "NVIDIA was approved for a defense procurement program after data center orders increased",
            "NVIDIA Army selected its chips after data center orders increased",
            "NVIDIA NATO adopted its platform after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_executive_leadership_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA appointed a new chief executive after data center orders increased",
            "NVIDIA named a new chief executive after data center orders increased",
            "NVIDIA hired a new chief operating officer after data center orders increased",
            "NVIDIA promoted a new president after data center orders increased",
            "NVIDIA replaced its chief executive after data center orders increased",
            "NVIDIA ousted its chief executive after data center orders increased",
            "NVIDIA chief executive resigned after data center orders increased",
            "NVIDIA finance chief stepped down after data center orders increased",
            "NVIDIA founder stepped aside after data center orders increased",
            "NVIDIA board reshuffled leadership after data center orders increased",
            "NVIDIA added a new board member after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_security_privacy_outage_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA suffered a data breach after data center orders increased",
            "NVIDIA was hacked after data center orders increased",
            "NVIDIA leaked customer data after data center orders increased",
            "NVIDIA exposed user data after data center orders increased",
            "NVIDIA confirmed a security incident after data center orders increased",
            "NVIDIA fixed a zero-day vulnerability after data center orders increased",
            "NVIDIA patched a critical vulnerability after data center orders increased",
            "NVIDIA faced a ransomware attack after data center orders increased",
            "NVIDIA outage affected users after data center orders increased",
            "NVIDIA service went offline after data center orders increased",
            "NVIDIA app went down after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_security_compliance_certification_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA achieved SOC 2 compliance after data center orders increased",
            "NVIDIA received ISO 27001 certification after data center orders increased",
            "NVIDIA earned FedRAMP authorization after data center orders increased",
            "NVIDIA became HIPAA compliant after data center orders increased",
            "NVIDIA met GDPR requirements after data center orders increased",
            "NVIDIA passed a security audit after data center orders increased",
            "NVIDIA completed a penetration test after data center orders increased",
            "NVIDIA resolved all vulnerabilities after data center orders increased",
            "NVIDIA achieved zero critical vulnerabilities after data center orders increased",
            "NVIDIA received FIPS certification after data center orders increased",
            "NVIDIA passed a compliance audit after data center orders increased",
            "NVIDIA earned a security certification after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_cybersecurity_privacy_detail_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA disclosed a data breach after data center orders increased",
            "NVIDIA customer data leaked after data center orders increased",
            "NVIDIA user records were exposed after data center orders increased",
            "NVIDIA credentials were stolen after data center orders increased",
            "NVIDIA passwords leaked online after data center orders increased",
            "NVIDIA attackers stole source code after data center orders increased",
            "NVIDIA source code was stolen after data center orders increased",
            "NVIDIA malware infected systems after data center orders increased",
            "NVIDIA phishing campaign targeted users after data center orders increased",
            "NVIDIA exploited a zero-day vulnerability after data center orders increased",
            "NVIDIA critical vulnerability was exploited after data center orders increased",
            "NVIDIA privacy violation exposed users after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_consumer_service_trust_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA issued refunds after data center orders increased",
            "NVIDIA offered compensation to users after data center orders increased",
            "NVIDIA gave service credits after data center orders increased",
            "NVIDIA customer complaints surged after data center orders increased",
            "NVIDIA users canceled subscriptions after data center orders increased",
            "NVIDIA subscription cancellations spiked after data center orders increased",
            "NVIDIA churn increased after data center orders increased",
            "NVIDIA retention fell after data center orders increased",
            "NVIDIA warranty claims rose after data center orders increased",
            "NVIDIA product returns increased after data center orders increased",
            "NVIDIA missed its uptime SLA after data center orders increased",
            "NVIDIA downtime triggered refunds after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_product_retention_paid_conversion_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA retention rose after data center orders increased",
            "NVIDIA retention improved after data center orders increased",
            "NVIDIA customer retention increased after data center orders increased",
            "NVIDIA user retention doubled after data center orders increased",
            "NVIDIA subscriber retention improved after data center orders increased",
            "NVIDIA churn fell after data center orders increased",
            "NVIDIA churn declined after data center orders increased",
            "NVIDIA customer churn dropped after data center orders increased",
            "NVIDIA net revenue retention rose after data center orders increased",
            "NVIDIA NRR increased after data center orders increased",
            "NVIDIA gross revenue retention improved after data center orders increased",
            "NVIDIA paying users increased after data center orders increased",
            "NVIDIA paid users doubled after data center orders increased",
            "NVIDIA free-to-paid conversion increased after data center orders increased",
            "NVIDIA trial conversion rose after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_customer_reliability_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA NPS improved after data center orders increased",
            "NVIDIA net promoter score rose after data center orders increased",
            "NVIDIA CSAT increased after data center orders increased",
            "NVIDIA customer satisfaction improved after data center orders increased",
            "NVIDIA user sentiment turned positive after data center orders increased",
            "NVIDIA brand trust increased after data center orders increased",
            "NVIDIA support tickets fell after data center orders increased",
            "NVIDIA bug reports dropped after data center orders increased",
            "NVIDIA crash rate fell after data center orders increased",
            "NVIDIA crashes declined after data center orders increased",
            "NVIDIA uptime improved after data center orders increased",
            "NVIDIA SLA compliance improved after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_customer_support_operations_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA refund rate increased after data center orders increased",
            "NVIDIA refund rates fell after data center orders increased",
            "NVIDIA chargeback rate rose after data center orders increased",
            "NVIDIA chargeback rates declined after data center orders increased",
            "NVIDIA customer complaints fell after data center orders increased",
            "NVIDIA complaint volume dropped after data center orders increased",
            "NVIDIA ticket backlog increased after data center orders increased",
            "NVIDIA support backlog fell after data center orders increased",
            "NVIDIA first response time improved after data center orders increased",
            "NVIDIA response times increased after data center orders increased",
            "NVIDIA resolution time dropped after data center orders increased",
            "NVIDIA average handle time fell after data center orders increased",
            "NVIDIA SLA breach rate rose after data center orders increased",
            "NVIDIA service credit requests increased after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_insurance_compensation_liability_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA insurance payout covered the outage after data center orders increased",
            "NVIDIA insurer denied coverage after data center orders increased",
            "NVIDIA premiums increased after data center orders increased",
            "NVIDIA liability coverage was exhausted after data center orders increased",
            "NVIDIA paid damages after data center orders increased",
            "NVIDIA was ordered to pay damages after data center orders increased",
            "NVIDIA reached a product liability settlement after data center orders increased",
            "NVIDIA created a settlement fund after data center orders increased",
            "NVIDIA reimbursed customers after data center orders increased",
            "NVIDIA extended warranties after data center orders increased",
            "NVIDIA offered recall reimbursements after data center orders increased",
            "NVIDIA insurance claim was denied after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_platform_moderation_distribution_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA app was removed from the App Store after data center orders increased",
            "NVIDIA was banned from Google Play after data center orders increased",
            "NVIDIA account was suspended after data center orders increased",
            "NVIDIA ads were banned after data center orders increased",
            "NVIDIA API access was revoked after data center orders increased",
            "NVIDIA developer account was terminated after data center orders increased",
            "NVIDIA was demonetized after data center orders increased",
            "NVIDIA posts were removed after data center orders increased",
            "NVIDIA content was flagged as misinformation after data center orders increased",
            "NVIDIA was shadowbanned after data center orders increased",
            "NVIDIA lost platform access after data center orders increased",
            "NVIDIA channel was taken down after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_corporate_transaction_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA acquired a startup after data center orders increased",
            "NVIDIA bought a startup after data center orders increased",
            "NVIDIA completed a merger after data center orders increased",
            "NVIDIA announced an acquisition after data center orders increased",
            "NVIDIA raised funding after data center orders increased",
            "NVIDIA closed a funding round after data center orders increased",
            "NVIDIA secured financing after data center orders increased",
            "NVIDIA sold a stake after data center orders increased",
            "NVIDIA spun off a unit after data center orders increased",
            "NVIDIA launched a buyback after data center orders increased",
            "NVIDIA declared a dividend after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_capital_markets_listing_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA filed for an IPO after data center orders increased",
            "NVIDIA filed confidentially for an IPO after data center orders increased",
            "NVIDIA launched an IPO after data center orders increased",
            "NVIDIA priced its IPO after data center orders increased",
            "NVIDIA delayed its IPO after data center orders increased",
            "NVIDIA went public after data center orders increased",
            "NVIDIA listed on Nasdaq after data center orders increased",
            "NVIDIA debuted on the NYSE after data center orders increased",
            "NVIDIA completed a SPAC merger after data center orders increased",
            "NVIDIA secured unicorn valuation after data center orders increased",
            "NVIDIA valuation doubled after data center orders increased",
            "NVIDIA launched a secondary offering after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_shareholder_capital_action_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA authorized a share repurchase after data center orders increased",
            "NVIDIA expanded its buyback after data center orders increased",
            "NVIDIA increased its dividend after data center orders increased",
            "NVIDIA cut its dividend after data center orders increased",
            "NVIDIA suspended its dividend after data center orders increased",
            "NVIDIA announced a stock split after data center orders increased",
            "NVIDIA completed a stock split after data center orders increased",
            "NVIDIA approved a reverse stock split after data center orders increased",
            "NVIDIA issued new shares after data center orders increased",
            "NVIDIA sold shares after data center orders increased",
            "NVIDIA filed a shelf offering after data center orders increased",
            "NVIDIA launched an at-the-market offering after data center orders increased",
            "NVIDIA raised capital through a share sale after data center orders increased",
            "NVIDIA completed a private placement after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_product_launch_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA launched a new chip after data center orders increased",
            "NVIDIA launched a new AI chip after data center orders increased",
            "NVIDIA unveiled a new GPU after data center orders increased",
            "NVIDIA released a new AI model after data center orders increased",
            "NVIDIA rolled out a new platform after data center orders increased",
            "NVIDIA debuted a new product after data center orders increased",
            "NVIDIA introduced a new service after data center orders increased",
            "NVIDIA shipped a new feature after data center orders increased",
            "NVIDIA opened preorders after data center orders increased",
            "NVIDIA started beta testing after data center orders increased",
            "NVIDIA made the product generally available after data center orders increased",
            "NVIDIA started mass production after data center orders increased",
            "NVIDIA delayed a product launch after data center orders increased",
            "NVIDIA cut GPU prices after data center orders increased",
            "NVIDIA raised chip prices after data center orders increased",
            "NVIDIA sold out a new chip after data center orders increased",
            "NVIDIA shipped the first units after data center orders increased",
            "NVIDIA halted shipments after data center orders increased",
            "NVIDIA expanded production capacity after data center orders increased",
            "NVIDIA reported supply shortages after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_operational_footprint_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA opened new stores after data center orders increased",
            "NVIDIA store count doubled after data center orders increased",
            "NVIDIA expanded into Europe after data center orders increased",
            "NVIDIA entered the Korean market after data center orders increased",
            "NVIDIA launched in Japan after data center orders increased",
            "NVIDIA opened a flagship store after data center orders increased",
            "NVIDIA expanded retail footprint after data center orders increased",
            "NVIDIA added distribution centers after data center orders increased",
            "NVIDIA opened new warehouses after data center orders increased",
            "NVIDIA began local production after data center orders increased",
            "NVIDIA localized local production after data center orders increased",
            "NVIDIA opened a regional headquarters after data center orders increased",
            "NVIDIA expanded presence in India after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_supply_availability_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA order backlog hit a record after data center orders increased",
            "NVIDIA backlog exceeded supply after data center orders increased",
            "NVIDIA lead times doubled after data center orders increased",
            "NVIDIA delivery times stretched after data center orders increased",
            "NVIDIA allocation tightened after data center orders increased",
            "NVIDIA inventory was depleted after data center orders increased",
            "NVIDIA inventory levels fell after data center orders increased",
            "NVIDIA channel inventory dried up after data center orders increased",
            "NVIDIA product availability improved after data center orders increased",
            "NVIDIA waitlist grew after data center orders increased",
            "NVIDIA order book filled after data center orders increased",
            "NVIDIA book-to-bill ratio rose after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_workforce_operations_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA announced layoffs after data center orders increased",
            "NVIDIA cut jobs after data center orders increased",
            "NVIDIA hired new engineers after data center orders increased",
            "NVIDIA opened a new factory after data center orders increased",
            "NVIDIA closed a plant after data center orders increased",
            "NVIDIA paused production after data center orders increased",
            "NVIDIA resumed production after data center orders increased",
            "NVIDIA expanded manufacturing after data center orders increased",
            "NVIDIA ramped production after data center orders increased",
            "NVIDIA shifted production after data center orders increased",
            "NVIDIA moved jobs overseas after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_workforce_metric_movement_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA headcount grew after data center orders increased",
            "NVIDIA headcount increased after data center orders increased",
            "NVIDIA workforce grew after data center orders increased",
            "NVIDIA workforce doubled after data center orders increased",
            "NVIDIA employee count doubled after data center orders increased",
            "NVIDIA employee count fell after data center orders increased",
            "NVIDIA staffing levels rose after data center orders increased",
            "NVIDIA hiring increased after data center orders increased",
            "NVIDIA hiring slowed after data center orders increased",
            "NVIDIA job openings fell after data center orders increased",
            "NVIDIA attrition rose after data center orders increased",
            "NVIDIA turnover declined after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_workforce_labor_extension_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA laid off employees after data center orders increased",
            "NVIDIA laid off workers after data center orders increased",
            "NVIDIA slashed its workforce after data center orders increased",
            "NVIDIA reduced headcount after data center orders increased",
            "NVIDIA froze hiring after data center orders increased",
            "NVIDIA rescinded job offers after data center orders increased",
            "NVIDIA closed offices after data center orders increased",
            "NVIDIA employees voted to strike after data center orders increased",
            "NVIDIA workers rejected a contract after data center orders increased",
            "NVIDIA union approved a contract after data center orders increased",
            "NVIDIA reached a labor agreement after data center orders increased",
            "NVIDIA ended a worker strike after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_manufacturing_quality_metric_claims_penalized(self):
        trend = ScoredTrend(keyword="TSMC", rank=1, top_insight="TSMC demand increased after AI chip orders")
        claims = (
            "TSMC yield rate improved after AI chip orders increased",
            "TSMC chip yields rose after AI chip orders increased",
            "TSMC production yield fell after AI chip orders increased",
            "TSMC defect rate declined after AI chip orders increased",
            "TSMC failure rate increased after AI chip orders increased",
            "TSMC scrap rate dropped after AI chip orders increased",
            "TSMC factory utilization rose after AI chip orders increased",
            "TSMC fab utilization improved after AI chip orders increased",
            "TSMC capacity utilization fell after AI chip orders increased",
            "TSMC production output increased after AI chip orders increased",
            "TSMC factory output rose after AI chip orders increased",
            "TSMC manufacturing output doubled after AI chip orders increased",
            "TSMC line efficiency improved after AI chip orders increased",
            "TSMC equipment uptime increased after AI chip orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_infrastructure_facility_capacity_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA opened a new data center after data center orders increased",
            "NVIDIA broke ground on a new data center after data center orders increased",
            "NVIDIA started construction of a new facility after data center orders increased",
            "NVIDIA leased data center capacity after data center orders increased",
            "NVIDIA secured power capacity after data center orders increased",
            "NVIDIA received a data center permit after data center orders increased",
            "NVIDIA bought land for a data center after data center orders increased",
            "NVIDIA won zoning approval after data center orders increased",
            "NVIDIA connected a new facility to the grid after data center orders increased",
            "NVIDIA completed a data center expansion after data center orders increased",
            "NVIDIA added megawatt capacity after data center orders increased",
            "NVIDIA signed a data center lease after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_compute_capacity_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA compute capacity doubled after data center orders increased",
            "NVIDIA cloud capacity increased after data center orders increased",
            "NVIDIA GPU cluster doubled after data center orders increased",
            "NVIDIA AI cluster expanded after data center orders increased",
            "NVIDIA training cluster grew after data center orders increased",
            "NVIDIA inference capacity rose after data center orders increased",
            "NVIDIA data center capacity expanded after data center orders increased",
            "NVIDIA datacenter capacity doubled after data center orders increased",
            "NVIDIA accelerator capacity increased after data center orders increased",
            "NVIDIA server fleet expanded after data center orders increased",
            "NVIDIA cloud region went live after data center orders increased",
            "NVIDIA availability zone launched after data center orders increased",
            "NVIDIA reserved compute capacity after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_workplace_labor_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA workers went on strike after data center orders increased",
            "NVIDIA employees staged a walkout after data center orders increased",
            "NVIDIA workers voted to unionize after data center orders increased",
            "NVIDIA union filed a complaint after data center orders increased",
            "NVIDIA labor board opened an investigation after data center orders increased",
            "NVIDIA faced wage theft claims after data center orders increased",
            "NVIDIA cut worker pay after data center orders increased",
            "NVIDIA employees alleged harassment after data center orders increased",
            "NVIDIA employees alleged discrimination after data center orders increased",
            "NVIDIA workplace injury was reported after data center orders increased",
            "NVIDIA OSHA opened an investigation after data center orders increased",
            "NVIDIA contract talks collapsed after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_regulatory_legal_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA received regulatory approval after data center orders increased",
            "NVIDIA secured antitrust clearance after data center orders increased",
            "NVIDIA won government approval after data center orders increased",
            "NVIDIA gained court approval after data center orders increased",
            "NVIDIA received an export license after data center orders increased",
            "NVIDIA won a license approval after data center orders increased",
            "NVIDIA cleared a legal hurdle after data center orders increased",
            "NVIDIA won a lawsuit after data center orders increased",
            "NVIDIA settled a lawsuit after data center orders increased",
            "NVIDIA reached a settlement after data center orders increased",
            "NVIDIA resolved a legal dispute after data center orders increased",
            "NVIDIA avoided a regulatory ban after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_ongoing_legal_regulatory_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA faces a lawsuit after data center orders increased",
            "NVIDIA was sued after data center orders increased",
            "NVIDIA is being sued after data center orders increased",
            "NVIDIA was hit with a class action after data center orders increased",
            "NVIDIA faces an antitrust probe after data center orders increased",
            "NVIDIA is under investigation after data center orders increased",
            "NVIDIA came under regulatory scrutiny after data center orders increased",
            "Regulators opened an investigation into NVIDIA after data center orders increased",
            "Authorities launched a probe into NVIDIA after data center orders increased",
            "The FTC sued NVIDIA after data center orders increased",
            "The DOJ investigated NVIDIA after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_intellectual_property_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA won a patent case after data center orders increased",
            "NVIDIA lost a patent dispute after data center orders increased",
            "NVIDIA patent was invalidated after data center orders increased",
            "NVIDIA patent was granted after data center orders increased",
            "NVIDIA filed a patent infringement lawsuit after data center orders increased",
            "NVIDIA faced patent infringement claims after data center orders increased",
            "NVIDIA settled a trademark dispute after data center orders increased",
            "NVIDIA received a copyright takedown after data center orders increased",
            "NVIDIA issued a DMCA notice after data center orders increased",
            "NVIDIA signed a royalty agreement after data center orders increased",
            "NVIDIA was accused of IP theft after data center orders increased",
            "NVIDIA trade secret case was dismissed after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_regulatory_enforcement_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA was fined by regulators after data center orders increased",
            "NVIDIA paid a penalty after data center orders increased",
            "NVIDIA agreed to pay a fine after data center orders increased",
            "NVIDIA received a subpoena after data center orders increased",
            "NVIDIA was sanctioned after data center orders increased",
            "NVIDIA faced export restrictions after data center orders increased",
            "NVIDIA was barred from selling chips after data center orders increased",
            "NVIDIA was banned from selling chips after data center orders increased",
            "Regulators imposed a penalty on NVIDIA after data center orders increased",
            "The SEC charged NVIDIA after data center orders increased",
            "The EU fined NVIDIA after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_trade_export_control_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA was hit by new tariffs after data center orders increased",
            "NVIDIA tariffs raised chip costs after data center orders increased",
            "NVIDIA was added to an export blacklist after data center orders increased",
            "NVIDIA was placed on the entity list after data center orders increased",
            "NVIDIA export license was denied after data center orders increased",
            "NVIDIA export license was revoked after data center orders increased",
            "NVIDIA faced new trade curbs after data center orders increased",
            "NVIDIA faced chip sales restrictions after data center orders increased",
            "NVIDIA chip sales were blocked by regulators after data center orders increased",
            "NVIDIA exports were blocked after data center orders increased",
            "NVIDIA shipments were banned under new export controls after data center orders increased",
            "NVIDIA lost access to China sales after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_criminal_misconduct_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA executive was arrested after data center orders increased",
            "NVIDIA CEO was indicted after data center orders increased",
            "NVIDIA was charged with fraud after data center orders increased",
            "NVIDIA admitted bribery after data center orders increased",
            "NVIDIA paid bribes after data center orders increased",
            "NVIDIA was accused of money laundering after data center orders increased",
            "NVIDIA employee pleaded guilty after data center orders increased",
            "NVIDIA was convicted of corruption after data center orders increased",
            "NVIDIA insider trading scheme surfaced after data center orders increased",
            "NVIDIA embezzled funds after data center orders increased",
            "NVIDIA falsified records after data center orders increased",
            "NVIDIA obstructed justice after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_passive_regulatory_legal_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "A court approved NVIDIA's settlement after data center orders increased",
            "A judge dismissed NVIDIA's lawsuit after data center orders increased",
            "NVIDIA's license was approved after data center orders increased",
            "NVIDIA's lawsuit was dismissed after data center orders increased",
            "NVIDIA's case was settled after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_financial_distress_accounting_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA filed for bankruptcy after data center orders increased",
            "NVIDIA is preparing for bankruptcy after data center orders increased",
            "NVIDIA defaulted on debt after data center orders increased",
            "NVIDIA missed a bond payment after data center orders increased",
            "NVIDIA warned of a going concern risk after data center orders increased",
            "NVIDIA was delisted after data center orders increased",
            "NVIDIA shares were halted after data center orders increased",
            "NVIDIA trading was suspended after data center orders increased",
            "NVIDIA restated earnings after data center orders increased",
            "NVIDIA disclosed accounting errors after data center orders increased",
            "NVIDIA auditor resigned after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_product_safety_recall_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA recalled a product after data center orders increased",
            "NVIDIA issued a recall after data center orders increased",
            "NVIDIA pulled devices from shelves after data center orders increased",
            "NVIDIA warned of a fire risk after data center orders increased",
            "NVIDIA confirmed a safety defect after data center orders increased",
            "NVIDIA reported injury claims after data center orders increased",
            "NVIDIA faces product safety complaints after data center orders increased",
            "NVIDIA halted shipments over safety concerns after data center orders increased",
            "NVIDIA received an FDA warning letter after data center orders increased",
            "NVIDIA announced a voluntary recall after data center orders increased",
            "NVIDIA expanded a product recall after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_medical_clinical_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA cured cancer after data center orders increased",
            "NVIDIA reduced mortality after data center orders increased",
            "NVIDIA improved patient survival after data center orders increased",
            "NVIDIA passed a clinical trial after data center orders increased",
            "NVIDIA failed a clinical trial after data center orders increased",
            "NVIDIA reported positive trial results after data center orders increased",
            "NVIDIA received FDA approval for a drug after data center orders increased",
            "NVIDIA got emergency use authorization after data center orders increased",
            "NVIDIA launched a new therapy after data center orders increased",
            "NVIDIA diagnosed patients after data center orders increased",
            "NVIDIA prevented heart attacks after data center orders increased",
            "NVIDIA vaccine showed efficacy after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_scientific_research_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA published a peer-reviewed study after data center orders increased",
            "NVIDIA study proved chips cut energy use after data center orders increased",
            "NVIDIA researchers confirmed a breakthrough after data center orders increased",
            "NVIDIA research debunked rivals after data center orders increased",
            "NVIDIA discovered a new material after data center orders increased",
            "NVIDIA invented a new algorithm after data center orders increased",
            "NVIDIA achieved quantum supremacy after data center orders increased",
            "NVIDIA won a Nobel Prize after data center orders increased",
            "NVIDIA received peer review acceptance after data center orders increased",
            "NVIDIA paper was published in Nature after data center orders increased",
            "NVIDIA replicated the findings after data center orders increased",
            "NVIDIA retracted a study after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_environmental_industrial_incident_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA caused an oil spill after data center orders increased",
            "NVIDIA reported a chemical leak after data center orders increased",
            "NVIDIA released toxic gas after data center orders increased",
            "NVIDIA violated emissions rules after data center orders increased",
            "NVIDIA exceeded pollution limits after data center orders increased",
            "NVIDIA plant exploded after data center orders increased",
            "NVIDIA factory fire injured workers after data center orders increased",
            "NVIDIA dumped wastewater after data center orders increased",
            "NVIDIA contaminated local water after data center orders increased",
            "NVIDIA received an environmental violation notice after data center orders increased",
            "NVIDIA halted operations after an environmental incident after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_sustainability_esg_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA became carbon neutral after data center orders increased",
            "NVIDIA reached net zero after data center orders increased",
            "NVIDIA cut carbon emissions after data center orders increased",
            "NVIDIA reduced water usage after data center orders increased",
            "NVIDIA powered facilities with renewable energy after data center orders increased",
            "NVIDIA signed a renewable energy deal after data center orders increased",
            "NVIDIA faced greenwashing allegations after data center orders increased",
            "NVIDIA was accused of greenwashing after data center orders increased",
            "NVIDIA failed an ESG audit after data center orders increased",
            "NVIDIA received a sustainability certification after data center orders increased",
            "NVIDIA missed climate targets after data center orders increased",
            "NVIDIA reported Scope 3 emissions increased after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_sustainability_metric_movement_claims_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")
        claims = (
            "NVIDIA energy consumption fell after data center orders increased",
            "NVIDIA electricity use doubled after data center orders increased",
            "NVIDIA carbon emissions declined after data center orders increased",
            "NVIDIA CO2 emissions fell after data center orders increased",
            "NVIDIA greenhouse gas emissions increased after data center orders increased",
            "NVIDIA GHG emissions dropped after data center orders increased",
            "NVIDIA emissions rose after data center orders increased",
            "NVIDIA Scope 1 emissions increased after data center orders increased",
            "NVIDIA Scope 2 emissions declined after data center orders increased",
            "NVIDIA Scope 3 emissions rose after data center orders increased",
            "NVIDIA water usage increased after data center orders increased",
            "NVIDIA water consumption dropped after data center orders increased",
            "NVIDIA renewable energy use rose after data center orders increased",
            "NVIDIA renewable energy share improved after data center orders increased",
            "NVIDIA power usage effectiveness improved after data center orders increased",
            "NVIDIA PUE improved after data center orders increased",
            "NVIDIA recycling rate increased after data center orders increased",
            "NVIDIA carbon footprint declined after data center orders increased",
            "NVIDIA emissions intensity improved after data center orders increased",
        )

        for claim in claims:
            score, violation, issues = _score_fact(claim, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported strong claim" in issue for issue in issues)


class TestScoreFactKoreanStrongClaims:
    def test_grounded_korean_record_high_claim_passes(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 역대 최고를 기록")

        score, violation, issues = _score_fact("NVIDIA 수요가 역대 최고를 기록했다", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_record_high_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "NVIDIA 수요가 데이터센터 주문 이후 역대 최고를 기록했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_korean_all_time_high_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "NVIDIA 수요가 데이터센터 주문 이후 사상 최고치를 기록했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_korean_first_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "NVIDIA가 데이터센터 주문 이후 최초로 수요 증가를 기록했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)

    def test_ungrounded_korean_largest_claim_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "NVIDIA가 데이터센터 주문 이후 최대 주문 사이클을 기록했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported strong claim" in issue for issue in issues)


class TestScoreFactDomainAttribution:
    def test_grounded_domain_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact("reuters.com reports NVIDIA demand increased after data center orders", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_domain_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("reuters.com reports NVIDIA demand increased after data center orders", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_ungrounded_according_to_domain_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "According to www.reuters.com, NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_grounded_via_domain_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact("Via reuters.com, NVIDIA demand increased after data center orders", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_source_domain_attribution_penalized_without_marker_entity_noise(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Source: reuters.com NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)
        assert not any("source" in issue and "고유명사" in issue for issue in issues)

    def test_grounded_reported_by_domain_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact(
            "NVIDIA demand increased after data center orders, reported by reuters.com",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_citing_domain_attribution_penalized_without_marker_entity_noise(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA demand increased after data center orders, citing reuters.com",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)
        assert not any("citing" in issue and "고유명사" in issue for issue in issues)

    def test_grounded_per_domain_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact("Per reuters.com, NVIDIA demand increased after data center orders", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_as_per_domain_attribution_penalized_without_marker_entity_noise(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "As per reuters.com, NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)
        assert not any(("as" in issue or "per" in issue) and "고유명사" in issue for issue in issues)

    def test_grounded_line_start_domain_label_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact("reuters.com: NVIDIA demand increased after data center orders", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_line_start_domain_label_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("reuters.com - NVIDIA demand increased after data center orders", trend)

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_grounded_korean_domain_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA 수요가 데이터센터 주문 이후 증가",
        )

        score, violation, issues = _score_fact(
            "reuters.com에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_domain_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "reuters.com 보도에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_grounded_korean_source_domain_label_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA 수요가 데이터센터 주문 이후 증가",
        )

        score, violation, issues = _score_fact(
            "출처: reuters.com NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_korean_source_domain_label_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "근거: reuters.com NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_grounded_domain_data_signal_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact(
            "reuters.com data shows NVIDIA demand increased after data center orders",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_domain_data_signal_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "reuters.com data shows NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)

    def test_grounded_evidence_from_domain_passes_without_marker_entity_noise(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="reuters.com NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact(
            "Data from reuters.com shows NVIDIA demand increased after data center orders",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_analysis_from_domain_penalized_without_marker_entity_noise(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Analysis from reuters.com suggests NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("unsupported source domain attribution" in issue for issue in issues)
        assert not any("analysis" in issue.casefold() and "고유명사" in issue for issue in issues)


class TestScoreFactOutletAttribution:
    def test_grounded_outlet_attribution_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="Reuters NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact("Reuters reported NVIDIA demand increased after data center orders", trend)

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_outlet_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            ("Reuters reported NVIDIA demand increased after data center orders", "reuters"),
            ("Bloomberg said NVIDIA demand increased after data center orders", "bloomberg"),
            ("Yonhap reported that NVIDIA demand increased after data center orders", "yonhap"),
            ("The Financial Times reported NVIDIA demand increased after data center orders", "financial times"),
            ("The Wall Street Journal said NVIDIA demand increased after data center orders", "wall street journal"),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported source outlet attribution" in issue for issue in issues)
            assert any(expected in issue for issue in issues if "unsupported source outlet attribution" in issue)

    def test_grounded_outlet_data_signal_passes(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="Reuters NVIDIA demand increased after data center orders",
        )

        score, violation, issues = _score_fact(
            "Reuters data shows NVIDIA demand increased after data center orders",
            trend,
        )

        assert score == 15
        assert violation is False
        assert issues == []

    def test_ungrounded_outlet_data_signal_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            ("Reuters data shows NVIDIA demand increased after data center orders", "reuters"),
            ("Bloomberg analysis suggests NVIDIA demand increased after data center orders", "bloomberg"),
            ("Data from Reuters shows NVIDIA demand increased after data center orders", "reuters"),
            ("Figures from the Financial Times indicate NVIDIA demand increased after data center orders", "financial times"),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any("unsupported source outlet attribution" in issue for issue in issues)
            assert any(expected in issue for issue in issues if "unsupported source outlet attribution" in issue)


class TestToneAnalogyGuard:
    def test_prohibited_analogy_is_penalized(self):
        content = "이 변화는 마치 예산표가 한 번에 흔들리는 상황 같다."
        score, issues = _score_tone(content, [_make_tweet(content)], [], None)
        assert score <= 7
        assert any("비유/은유" in issue for issue in issues)


# ===========================================================================
# 5. Unverified Quote Pattern Detection
# ===========================================================================


class TestUnverifiedQuotes:
    def test_all_patterns_are_korean(self):
        """Sanity check: all patterns should be non-empty Korean strings."""
        for pattern in _UNVERIFIED_QUOTE_PATTERNS:
            assert len(pattern) > 0
            # Korean characters in range
            assert any("\uac00" <= c <= "\ud7af" for c in pattern)

    def test_patterns_match_in_text(self):
        for pattern in _UNVERIFIED_QUOTE_PATTERNS:
            text = f"이번 사안에 대해 {pattern} 밝혔다."
            assert pattern in text


    def test_vague_english_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact("Sources say NVIDIA demand increased after data center orders", trend)

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_reportedly_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA reportedly increased demand after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("reportedly" in issue.lower() for issue in issues)

    def test_allegedly_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA allegedly increased demand after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("allegedly" in issue.lower() for issue in issues)

    def test_passive_said_to_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA is said to have increased demand after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("said to" in issue.lower() for issue in issues)

    def test_passive_understood_thought_tipped_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            ("NVIDIA is understood to have increased demand after data center orders", "understood to"),
            ("NVIDIA is thought to have increased demand after data center orders", "thought to"),
            ("NVIDIA is tipped to increase demand after data center orders", "tipped to"),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_passive_that_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            ("It is believed that NVIDIA demand increased after data center orders", "it is believed that"),
            ("It is understood that NVIDIA demand increased after data center orders", "it is understood that"),
            ("It is reported that NVIDIA demand increased after data center orders", "it is reported that"),
            ("It is expected that NVIDIA demand increased after data center orders", "it is expected that"),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_person_familiar_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "A person familiar with the matter says NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("familiar with the matter" in issue.lower() for issue in issues)

    def test_source_familiar_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "A source familiar with the matter says NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("source familiar with the matter" in issue.lower() for issue in issues)

    def test_according_to_source_familiar_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "According to a source familiar with the matter, NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("according to a source familiar" in issue.lower() for issue in issues)

    def test_according_to_quantified_source_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "According to two sources, NVIDIA demand increased after data center orders",
                "according to two sources",
            ),
            (
                "According to multiple insiders, NVIDIA demand increased after data center orders",
                "according to multiple insiders",
            ),
            (
                "According to several people familiar with the plans, NVIDIA demand increased after data center orders",
                "according to several people familiar with the plans",
            ),
            (
                "According to two people briefed on the decision, NVIDIA demand increased after data center orders",
                "according to two people briefed on the decision",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_non_matter_familiar_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "People familiar with the plans said NVIDIA demand increased after data center orders",
                "familiar with the plans said",
            ),
            (
                "A person familiar with the decision said NVIDIA demand increased after data center orders",
                "familiar with the decision said",
            ),
            (
                "Sources familiar with the talks said NVIDIA demand increased after data center orders",
                "familiar with the talks said",
            ),
            (
                "According to people familiar with the discussions, NVIDIA demand increased after data center orders",
                "according to people familiar with the discussions",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_briefed_and_knowledge_matter_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "A person briefed on the matter said NVIDIA demand increased after data center orders",
                "briefed on the matter",
            ),
            (
                "People with knowledge of the matter said NVIDIA demand increased after data center orders",
                "knowledge of the matter",
            ),
            (
                "Sources close to the matter said NVIDIA demand increased after data center orders",
                "close to the matter",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_according_to_briefed_or_knowledge_matter_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "According to people briefed on the matter, NVIDIA demand increased after data center orders",
                "according to people briefed",
            ),
            (
                "According to people with knowledge of the matter, NVIDIA demand increased after data center orders",
                "according to people with knowledge",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_non_matter_briefed_knowledge_or_close_to_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "A person with knowledge of the decision said NVIDIA demand increased after data center orders",
                "knowledge of the decision said",
            ),
            (
                "People with direct knowledge of the deal said NVIDIA demand increased after data center orders",
                "direct knowledge of the deal said",
            ),
            (
                "Sources briefed on the talks said NVIDIA demand increased after data center orders",
                "briefed on the talks said",
            ),
            (
                "An insider close to the negotiations said NVIDIA demand increased after data center orders",
                "close to the negotiations said",
            ),
            (
                "According to people with first-hand knowledge of the discussions, "
                "NVIDIA demand increased after data center orders",
                "according to people with first-hand knowledge of the discussions",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_anonymity_condition_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text in [
            "A source speaking on condition of anonymity said NVIDIA demand increased after data center orders",
            "NVIDIA demand increased after data center orders, said a source speaking on condition of anonymity",
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any("condition of anonymity" in issue.lower() for issue in issues)

    def test_not_authorized_to_speak_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "An official not authorized to speak publicly said NVIDIA demand increased after data center orders",
                "not authorized to speak publicly",
            ),
            (
                "A source not authorized to discuss the matter said NVIDIA demand increased after data center orders",
                "not authorized to discuss the matter",
            ),
            (
                "People not authorized to speak publicly said NVIDIA demand increased after data center orders",
                "not authorized to speak publicly",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_requested_anonymity_or_unnamed_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "A person who asked not to be named said NVIDIA demand increased after data center orders",
                "asked not to be named",
            ),
            (
                "The official requested anonymity because they were not authorized to speak publicly and said "
                "NVIDIA demand increased after data center orders",
                "requested anonymity",
            ),
            (
                "A source declined to be identified and said NVIDIA demand increased after data center orders",
                "declined to be identified",
            ),
            (
                "A person spoke anonymously and said NVIDIA demand increased after data center orders",
                "spoke anonymously",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_source_indicate_or_suggest_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            ("Sources indicate NVIDIA demand increased after data center orders", "sources indicate"),
            ("Sources suggest NVIDIA demand increased after data center orders", "sources suggest"),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_source_told_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Sources told Reuters NVIDIA demand increased after data center orders",
                "sources told",
            ),
            (
                "A person familiar with the plans told Reuters NVIDIA demand increased after data center orders",
                "familiar with the plans told",
            ),
            (
                "An official not authorized to discuss the matter told reporters "
                "NVIDIA demand increased after data center orders",
                "not authorized to discuss the matter told",
            ),
            (
                "People briefed on the talks told Bloomberg NVIDIA demand increased after data center orders",
                "briefed on the talks told",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_generic_person_people_or_official_source_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Officials said NVIDIA demand increased after data center orders",
                "officials said",
            ),
            (
                "Officials told Reuters NVIDIA demand increased after data center orders",
                "officials told",
            ),
            (
                "People said NVIDIA demand increased after data center orders",
                "people said",
            ),
            (
                "A person told reporters NVIDIA demand increased after data center orders",
                "a person told",
            ),
            (
                "One official said NVIDIA demand increased after data center orders",
                "one official said",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_report_subject_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Several reports suggest NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("reports suggest" in issue.lower() for issue in issues)

    def test_media_outlet_subject_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Media outlets reported NVIDIA demand increased after data center orders",
                "media outlets reported",
            ),
            (
                "A newswire said NVIDIA demand increased after data center orders",
                "newswire said",
            ),
            (
                "Local media reported NVIDIA demand increased after data center orders",
                "local media reported",
            ),
            (
                "News outlets claimed NVIDIA demand increased after data center orders",
                "news outlets claimed",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_analyst_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Analysts say NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("analysts say" in issue.lower() for issue in issues)

    def test_according_to_analysts_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "NVIDIA demand increased after data center orders, according to analysts",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("according to analysts" in issue.lower() for issue in issues)

    def test_market_consensus_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Analysts forecast NVIDIA demand will rise after data center orders",
                "analysts forecast",
            ),
            (
                "Wall Street is betting on NVIDIA demand after data center orders",
                "wall street is betting on",
            ),
            (
                "Investors are pricing in stronger NVIDIA demand after data center orders",
                "investors are pricing in",
            ),
            (
                "Traders expect NVIDIA shares to rise after data center orders",
                "traders expect",
            ),
            (
                "The market sees NVIDIA demand rising after data center orders",
                "the market sees",
            ),
            (
                "Consensus points to NVIDIA demand growth after data center orders",
                "consensus points to",
            ),
            (
                "Bulls say NVIDIA demand will rise after data center orders",
                "bulls say",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_leaked_roadmap_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "A leaked roadmap suggests NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_internal_memo_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "An internal memo says NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_document_subject_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "A filing indicates NVIDIA demand increased after data center orders",
                "filing indicates",
            ),
            (
                "A memo reveals NVIDIA demand increased after data center orders",
                "memo reveals",
            ),
            (
                "A presentation suggests NVIDIA demand increased after data center orders",
                "presentation suggests",
            ),
            (
                "A slide deck shows NVIDIA demand increased after data center orders",
                "slide deck shows",
            ),
            (
                "A spreadsheet indicates NVIDIA demand increased after data center orders",
                "spreadsheet indicates",
            ),
            (
                "A screenshot suggests NVIDIA demand increased after data center orders",
                "screenshot suggests",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_documents_seen_or_obtained_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Documents seen by reporters show NVIDIA demand increased after data center orders",
                "documents seen by",
            ),
            (
                "A document obtained by reporters says NVIDIA demand increased after data center orders",
                "document obtained by",
            ),
            (
                "A draft filing reviewed by reporters says NVIDIA demand increased after data center orders",
                "draft filing reviewed by",
            ),
            (
                "A presentation viewed by reporters suggests NVIDIA demand increased after data center orders",
                "presentation viewed by",
            ),
            (
                "Slides obtained by reporters indicate NVIDIA demand increased after data center orders",
                "slides obtained by",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_document_basis_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "According to documents reviewed by reporters, NVIDIA demand increased after data center orders",
                "according to documents reviewed",
            ),
            (
                "Based on a memo reviewed by reporters, NVIDIA demand increased after data center orders",
                "based on a memo reviewed",
            ),
            (
                "Citing documents reviewed by reporters, NVIDIA demand increased after data center orders",
                "citing documents reviewed",
            ),
            (
                "Citing a presentation obtained by reporters, NVIDIA demand increased after data center orders",
                "citing a presentation obtained",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_reporter_document_action_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Reporters reviewed documents showing NVIDIA demand increased after data center orders",
                "reviewed documents showing",
            ),
            (
                "Journalists obtained a memo claiming NVIDIA demand increased after data center orders",
                "obtained a memo claiming",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_korean_leaked_document_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "유출 문서에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_korean_internal_memo_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "내부 메모에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_korean_expert_sentence_attribution_penalized(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00",
        )

        score, violation, issues = _score_fact(
            "\uc804\ubb38\uac00\ub4e4\uc740 NVIDIA \uc218\uc694\uac00 "
            "\ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 "
            "\uc99d\uac00\ud588\ub2e4\uace0 \ubcf4\uace0 \uc788\ub2e4",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("\uc804\ubb38\uac00" in issue for issue in issues)

    def test_korean_industry_official_sentence_attribution_penalized(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00",
        )

        score, violation, issues = _score_fact(
            "\uc5c5\uacc4 \uad00\uacc4\uc790\ub4e4\uc740 NVIDIA \uc218\uc694\uac00 "
            "\ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 "
            "\uc99d\uac00\ud588\ub2e4\uace0 \ub9d0\ud55c\ub2e4",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("\uad00\uacc4\uc790" in issue for issue in issues)

    def test_korean_report_attribution_penalized(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00",
        )

        score, violation, issues = _score_fact(
            "\ubcf5\uc218\uc758 \ubcf4\ub3c4\uc5d0 \ub530\ub974\uba74 NVIDIA "
            "\uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 "
            "\uc774\ud6c4 \uc99d\uac00\ud588\ub2e4",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("\ubcf4\ub3c4" in issue for issue in issues)

    def test_korean_relation_source_attribution_penalized(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00",
        )

        score, violation, issues = _score_fact(
            "\uad00\uacc4\uc790\ub4e4\uc5d0 \ub530\ub974\uba74 NVIDIA "
            "\uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 "
            "\uc774\ud6c4 \uc99d\uac00\ud588\ub2e4",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("\uad00\uacc4\uc790" in issue for issue in issues)

    def test_korean_passive_sourcing_attribution_penalized(self):
        trend = ScoredTrend(
            keyword="NVIDIA",
            rank=1,
            top_insight="NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 \uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00",
        )

        for text, expected in [
            (
                "NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 "
                "\uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00\ud55c \uac83\uc73c\ub85c \uc54c\ub824\uc84c\ub2e4",
                "\uc54c\ub824\uc84c\ub2e4",
            ),
            (
                "NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 "
                "\uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00\ud55c \uac83\uc73c\ub85c \uc804\ud574\uc84c\ub2e4",
                "\uc804\ud574\uc84c\ub2e4",
            ),
            (
                "NVIDIA \uc218\uc694\uac00 \ub370\uc774\ud130\uc13c\ud130 "
                "\uc8fc\ubb38 \uc774\ud6c4 \uc99d\uac00\ud560 \uac83\uc73c\ub85c \uc804\ub9dd\ub41c\ub2e4",
                "\uc804\ub9dd\ub41c\ub2e4",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue for issue in issues)

    def test_rumor_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Rumors suggest NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_market_chatter_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        score, violation, issues = _score_fact(
            "Market chatter says NVIDIA demand increased after data center orders",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_social_thread_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "Threads say NVIDIA demand increased after data center orders",
                "threads say",
            ),
            (
                "A thread claims NVIDIA demand increased after data center orders",
                "a thread claims",
            ),
            (
                "A post says NVIDIA demand increased after data center orders",
                "a post says",
            ),
            (
                "A forum post suggests NVIDIA demand increased after data center orders",
                "a forum post suggests",
            ),
            (
                "A discussion thread indicates NVIDIA demand increased after data center orders",
                "a discussion thread indicates",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_survey_data_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA demand increased after data center orders")

        for text, expected in [
            (
                "A survey shows NVIDIA demand increased after data center orders",
                "a survey shows",
            ),
            (
                "A poll finds NVIDIA demand increased after data center orders",
                "a poll finds",
            ),
            (
                "A study suggests NVIDIA demand increased after data center orders",
                "a study suggests",
            ),
            (
                "A report finds NVIDIA demand increased after data center orders",
                "a report finds",
            ),
            (
                "Data shows NVIDIA demand increased after data center orders",
                "data shows",
            ),
            (
                "Figures indicate NVIDIA demand increased after data center orders",
                "figures indicate",
            ),
            (
                "Numbers suggest NVIDIA demand increased after data center orders",
                "numbers suggest",
            ),
            (
                "A dataset indicates NVIDIA demand increased after data center orders",
                "a dataset indicates",
            ),
            (
                "A tracker shows NVIDIA demand increased after data center orders",
                "a tracker shows",
            ),
        ]:
            score, violation, issues = _score_fact(text, trend)

            assert score < 15
            assert violation is True
            assert any(expected in issue.lower() for issue in issues)

    def test_korean_rumor_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "온라인 루머에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)

    def test_korean_market_rumor_attribution_penalized(self):
        trend = ScoredTrend(keyword="NVIDIA", rank=1, top_insight="NVIDIA 수요가 데이터센터 주문 이후 증가")

        score, violation, issues = _score_fact(
            "시장 소문에 따르면 NVIDIA 수요가 데이터센터 주문 이후 증가했다",
            trend,
        )

        assert score < 15
        assert violation is True
        assert any("출처 불명 인용" in issue for issue in issues)


class TestBuildRegenerationFeedback:
    def test_cross_platform_duplicate_drafts_are_failed(self):
        content = (
            "AI demand is lifting cloud budgets while chip supply remains tight. "
            "Operators need margin, latency, and capex checks before chasing the rally. "
            "That makes procurement discipline the real signal."
        )
        batch = TweetBatch(
            topic="AI demand",
            tweets=[GeneratedTweet(tweet_type="analysis", content=content, platform="x")],
            threads_posts=[GeneratedTweet(tweet_type="conversation", content=content, platform="threads")],
        )
        trend = ScoredTrend(keyword="AI demand", rank=1, top_insight=content)

        qa = asyncio.run(content_qa.audit_generated_content(batch, trend, AppConfig(), SimpleNamespace()))

        assert "threads_posts" in qa["failed_groups"]
        assert any(
            "cross-platform duplicate generated draft" in issue
            for issue in qa["group_results"]["threads_posts"]["issues"]
        )

    def test_distinct_cross_platform_drafts_pass_duplicate_guardrail(self):
        tweet = (
            "AI demand is lifting cloud budgets while chip supply remains tight. "
            "Operators need margin, latency, and capex checks before chasing the rally. "
            "That makes procurement discipline the real signal."
        )
        thread = (
            "AI app demand is changing where teams spend first. "
            "Inference costs, product retention, and data access now matter more than raw model hype. "
            "That shifts the signal toward execution quality."
        )
        batch = TweetBatch(
            topic="AI demand",
            tweets=[GeneratedTweet(tweet_type="analysis", content=tweet, platform="x")],
            threads_posts=[GeneratedTweet(tweet_type="conversation", content=thread, platform="threads")],
        )
        trend = ScoredTrend(keyword="AI demand", rank=1, top_insight=f"{tweet} {thread}")

        qa = asyncio.run(content_qa.audit_generated_content(batch, trend, AppConfig(), SimpleNamespace()))

        assert not any(
            "cross-platform duplicate generated draft" in issue
            for result in qa["group_results"].values()
            for issue in result["issues"]
        )

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


class TestRegenerateContentGroups:
    def test_regenerates_requested_groups_with_merged_feedback(self, monkeypatch):
        calls: dict[str, dict | str] = {}

        async def fake_tweets(*args, revision_feedback=None):
            calls["tweets_feedback"] = revision_feedback
            return SimpleNamespace(tweets=[_make_tweet("new tweet")])

        async def fake_threads(*args, revision_feedback=None):
            calls["threads_feedback"] = revision_feedback
            return [_make_tweet("new thread", platform="threads")]

        async def fake_long(*args, tier=None, revision_feedback=None):
            calls["long_tier"] = tier
            calls["long_feedback"] = revision_feedback
            return [_make_tweet("new long", platform="long")]

        async def fake_blog(*args, revision_feedback=None):
            calls["blog_feedback"] = revision_feedback
            return [_make_tweet("new blog", platform="naver_blog")]

        monkeypatch.setattr(
            content_qa,
            "_load_regeneration_generators",
            lambda: {
                "select_generation_tier": lambda trend, config: "premium",
                "generate_blog": fake_blog,
                "generate_long_form": fake_long,
                "generate_threads": fake_threads,
                "generate_tweets": fake_tweets,
            },
        )

        batch = TweetBatch(topic="old", tweets=[_make_tweet("old tweet")])
        trend = ScoredTrend(keyword="trend", rank=1, viral_potential=85)
        config = SimpleNamespace(
            enable_long_form=True,
            long_form_min_score=70,
            target_platforms=["naver_blog"],
            blog_min_score=70,
        )

        result = asyncio.run(
            regenerate_content_groups(
                batch,
                trend,
                config,
                client=SimpleNamespace(),
                groups=["tweets", "threads_posts", "long_posts", "blog_posts"],
                qa_feedback={"tweets": {"qa": {"total": 60}}},
                fact_check_feedback={"tweets": {"fact_check": {"hallucinated_claims": 1}}},
            )
        )

        assert result is batch
        assert batch.tweets[0].content == "new tweet"
        assert batch.threads_posts[0].content == "new thread"
        assert batch.long_posts[0].content == "new long"
        assert batch.blog_posts[0].content == "new blog"
        assert calls["long_tier"] == "premium"
        assert calls["tweets_feedback"] == {"qa": {"total": 60}, "fact_check": {"hallucinated_claims": 1}}
