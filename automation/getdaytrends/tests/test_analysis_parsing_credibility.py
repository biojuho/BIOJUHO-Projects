from __future__ import annotations

from types import SimpleNamespace

from analysis.parsing import _apply_credibility_check
from models import MultiSourceContext


def _context() -> MultiSourceContext:
    return MultiSourceContext(news_insight="low credibility source")


def test_apply_credibility_check_penalizes_low_credibility(monkeypatch):
    def fake_confidence(score, context, news_insight):
        return score, 0.2

    def fake_consistency(trend):
        return {"consistent": True, "conflicts": []}

    monkeypatch.setattr(
        "analysis.parsing._credibility_functions",
        lambda: (fake_consistency, fake_confidence),
    )
    config = SimpleNamespace(
        enable_source_credibility=True,
        credibility_penalty_threshold=0.3,
        credibility_penalty_factor=0.5,
        enable_cross_source_consistency=True,
    )

    score, credibility, consistent, flags = _apply_credibility_check(config, _context(), "AI", 80)

    assert score == 40
    assert credibility == 0.2
    assert consistent is True
    assert flags == []


def test_apply_credibility_check_limits_cross_source_conflict_flags(monkeypatch):
    def fake_confidence(score, context, news_insight):
        return score, 0.9

    def fake_consistency(trend):
        return {"consistent": False, "conflicts": ["one", "two", "three", "four"]}

    monkeypatch.setattr(
        "analysis.parsing._credibility_functions",
        lambda: (fake_consistency, fake_confidence),
    )
    config = SimpleNamespace(enable_source_credibility=True, enable_cross_source_consistency=True)

    score, credibility, consistent, flags = _apply_credibility_check(config, _context(), "AI", 80)

    assert score == 80
    assert credibility == 0.9
    assert consistent is False
    assert flags == [
        "cross-source conflict: one",
        "cross-source conflict: two",
        "cross-source conflict: three",
    ]
