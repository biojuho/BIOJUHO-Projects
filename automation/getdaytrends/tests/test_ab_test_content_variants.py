"""Offline tests for scripts/ab_test_content_variants.py.

These exercise the comparison/scoring/decision logic with injected generators,
so no LLM budget is spent. The --live generation path is intentionally not
covered here (it spends API budget and is run manually).
"""

import pytest
from config import AppConfig
from models import GeneratedTweet, ScoredTrend, TweetBatch
from scripts.ab_test_content_variants import (
    compare_trend_variants,
    decide_winner,
    run_ab,
    score_tweet_batch,
)


@pytest.fixture(scope="module")
def config():
    return AppConfig.from_env()


@pytest.fixture
def trend():
    return ScoredTrend(keyword="엔비디아", rank=1, top_insight="엔비디아 데이터센터 수요 증가")


def _batch(content: str) -> TweetBatch:
    return TweetBatch(
        topic="엔비디아",
        tweets=[GeneratedTweet(tweet_type="공감 유도형", content=content)],
    )


_GOOD = "엔비디아 실적이 시장 기대를 넘었다. 데이터센터 수요가 핵심 동력이다. 다음 분기 가이던스가 진짜 시험대다."


# ── decide_winner (pure) ──────────────────────────────────────────────────────


class TestDecideWinner:
    def test_b_wins_when_higher_and_no_new_failure(self):
        a = {"generated": True, "total": 70, "failed": False}
        b = {"generated": True, "total": 85, "failed": False}
        assert decide_winner(a, b) == "B"

    def test_a_wins_when_higher(self):
        a = {"generated": True, "total": 90, "failed": False}
        b = {"generated": True, "total": 80, "failed": False}
        assert decide_winner(a, b) == "A"

    def test_tie_keeps_a(self):
        a = {"generated": True, "total": 80, "failed": False}
        b = {"generated": True, "total": 80, "failed": False}
        assert decide_winner(a, b) == "A"

    def test_b_higher_but_adds_failure_keeps_a(self):
        a = {"generated": True, "total": 70, "failed": False}
        b = {"generated": True, "total": 95, "failed": True}
        assert decide_winner(a, b) == "A"

    def test_b_not_generated_keeps_a(self):
        a = {"generated": True, "total": 70, "failed": False}
        assert decide_winner(a, {"generated": False}) == "A"

    def test_a_not_generated_picks_b(self):
        b = {"generated": True, "total": 70, "failed": False}
        assert decide_winner({"generated": False}, b) == "B"

    def test_neither_generated_is_none(self):
        assert decide_winner({"generated": False}, {"generated": False}) == "none"


# ── score_tweet_batch ─────────────────────────────────────────────────────────


class TestScoreTweetBatch:
    def test_none_batch_not_generated(self, trend, config):
        s = score_tweet_batch(None, trend, config)
        assert s["generated"] is False
        assert s["n"] == 0

    def test_empty_batch_not_generated(self, trend, config):
        s = score_tweet_batch(TweetBatch(topic="엔비디아", tweets=[]), trend, config)
        assert s["generated"] is False

    def test_real_batch_scored(self, trend, config):
        s = score_tweet_batch(_batch(_GOOD), trend, config)
        assert s["generated"] is True
        assert s["n"] == 1
        assert s["total"] > 0


# ── run_ab aggregation + decision ─────────────────────────────────────────────


class TestRunAb:
    @pytest.mark.asyncio
    async def test_adopts_b_when_better(self, trend, config):
        weak = "엔비디아 좋다 대박 ㅋㅋ"  # short, low-quality lead
        strong = _GOOD

        async def gen_a(_t):
            return _batch(weak)

        async def gen_b(_t):
            return _batch(strong)

        summary = await run_ab([trend], config, gen_a, gen_b)
        assert summary["compared"] == 1
        # B is the stronger copy; if it scores higher it must be adopted.
        if summary["avg_b"] > summary["avg_a"]:
            assert summary["decision"] == "adopt_B"
            assert summary["b_wins"] == 1

    @pytest.mark.asyncio
    async def test_keeps_a_when_b_fails_to_generate(self, trend, config):
        async def gen_a(_t):
            return _batch(_GOOD)

        async def gen_b(_t):
            return None

        summary = await run_ab([trend], config, gen_a, gen_b)
        assert summary["decision"] == "keep_A"
        assert summary["compared"] == 0
        assert summary["a_wins"] == 1

    @pytest.mark.asyncio
    async def test_compare_trend_variants_shape(self, trend, config):
        async def gen(_t):
            return _batch(_GOOD)

        result = await compare_trend_variants(trend, config, gen, gen)
        assert result["keyword"] == "엔비디아"
        assert result["winner"] == "A"  # identical inputs → tie → keep A
        assert result["delta"] == 0
