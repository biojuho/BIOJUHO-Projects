"""Tests for the LLM-judge harness pure logic (order-bias mapping + decision).

The position-swap that cancels judge order bias is easy to get backwards — a sign
error would silently invert every A/B verdict — so it is pinned here.
"""

from scripts.ab_judge_content import _judge_decision, _winner_from_verdict


class TestWinnerFromVerdict:
    def test_a_shown_first_judge_picks_first_is_a(self):
        assert _winner_from_verdict("A", a_first=True) == "A"

    def test_a_shown_first_judge_picks_second_is_b(self):
        assert _winner_from_verdict("B", a_first=True) == "B"

    def test_swapped_judge_picks_first_is_really_b(self):
        # a_first False => B was shown first => judge's 'A' (first) means real B.
        assert _winner_from_verdict("A", a_first=False) == "B"

    def test_swapped_judge_picks_second_is_really_a(self):
        assert _winner_from_verdict("B", a_first=False) == "A"

    def test_non_ab_verdict_is_tie(self):
        assert _winner_from_verdict("?", a_first=True) == "tie"
        assert _winner_from_verdict("", a_first=False) == "tie"


class TestJudgeDecision:
    def test_adopts_b_on_clear_majority(self):
        assert _judge_decision(a_wins=1, b_wins=4, compared=5) == "adopt_B"

    def test_keeps_a_on_narrow_margin(self):
        # margin of 1 is not enough even with a B lead
        assert _judge_decision(a_wins=2, b_wins=3, compared=5) == "keep_A"

    def test_keeps_a_on_small_sample(self):
        assert _judge_decision(a_wins=0, b_wins=2, compared=2) == "keep_A"

    def test_tie_keeps_a(self):
        assert _judge_decision(a_wins=2, b_wins=2, compared=4) == "keep_A"
