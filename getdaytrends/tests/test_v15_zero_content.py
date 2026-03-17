# -*- coding: utf-8 -*-
"""
v15.0 Phase A Tests
  A-1: Dynamic category filter enhancement (zero-content prevention)
  A-2: Niche-First scoring
  A-3: Lazy Context config validation
"""
import pytest
from models import MultiSourceContext, ScoredTrend


def _make_scored_trend(
    keyword: str = "테스트트렌드",
    viral: int = 75,
    safety: bool = False,
    category: str = "",
    publishable: bool = True,
):
    """ScoredTrend factory with category support."""
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral,
        trend_acceleration="+5%",
        top_insight="테스트 인사이트",
        suggested_angles=["각도1", "각도2"],
        best_hook_starter="최고의 훅",
        context=MultiSourceContext(
            twitter_insight="X 반응", reddit_insight="Reddit 반응"
        ),
        safety_flag=safety,
        sentiment="harmful" if safety else "neutral",
        category=category,
        publishable=publishable,
    )


# ═══════════════════════════════════════════════
#  A-1: Zero Content Prevention
# ═══════════════════════════════════════════════

class TestZeroContentPrevention:
    """All trends are in exclude_categories -> return at least 1."""

    def _get_quality_func(self):
        from main import _ensure_quality_and_diversity
        return _ensure_quality_and_diversity

    def _make_config(self, **overrides):
        from config import AppConfig
        cfg = AppConfig()
        cfg.storage_type = "none"
        cfg.dry_run = True
        cfg.enable_clustering = False
        cfg.enable_sentiment_filter = True
        cfg.min_viral_score = 60
        cfg.exclude_categories = ["정치", "연예"]
        cfg.enable_zero_content_prevention = True
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg

    def test_all_excluded_returns_at_least_one(self):
        """Only entertainment trends x5 -> zero-content prevention returns >=1."""
        func = self._get_quality_func()
        config = self._make_config()

        trends = [
            _make_scored_trend("아이돌A", viral=95, category="연예"),
            _make_scored_trend("아이돌B", viral=88, category="연예"),
            _make_scored_trend("아이돌C", viral=73, category="연예"),
            _make_scored_trend("이슈태그D", viral=46, category="연예"),
            _make_scored_trend("이슈태그E", viral=24, category="연예"),
        ]

        result = func(trends, config)
        assert len(result) >= 1, f"Zero content prevention failed: {len(result)} returned"
        # safety_flag=False only
        for t in result:
            assert not t.safety_flag, f"safety_flag trend included: {t.keyword}"

    def test_all_excluded_with_low_scores_step2(self):
        """All excluded + all below min_viral_score -> step 2 relaxation (60% threshold)."""
        func = self._get_quality_func()
        config = self._make_config(min_viral_score=70)

        trends = [
            _make_scored_trend("연예뉴스A", viral=55, category="연예"),
            _make_scored_trend("연예뉴스B", viral=50, category="연예"),
            _make_scored_trend("정치이슈C", viral=45, category="정치"),
        ]

        result = func(trends, config)
        # Step 2: floor = 70 * 0.6 = 42 -> 55, 50, 45 all pass
        assert len(result) >= 1, f"Step 2 relaxation failed: {len(result)} returned"

    def test_safety_flag_never_included_in_prevention(self):
        """Zero content prevention never includes safety_flag=True trends."""
        func = self._get_quality_func()
        config = self._make_config()

        trends = [
            _make_scored_trend("위험트렌드", viral=95, category="연예", safety=True),
            _make_scored_trend("정상연예", viral=80, category="연예"),
        ]

        result = func(trends, config)
        for t in result:
            assert not t.safety_flag, f"safety_flag trend included: {t.keyword}"

    def test_prevention_disabled(self):
        """enable_zero_content_prevention=False -> normal behavior (0 returned)."""
        func = self._get_quality_func()
        config = self._make_config(enable_zero_content_prevention=False)

        trends = [
            _make_scored_trend("아이돌A", viral=95, category="연예"),
            _make_scored_trend("아이돌B", viral=80, category="연예"),
        ]

        result = func(trends, config)
        assert len(result) == 0, "Disabled should return 0"

    def test_non_excluded_category_unaffected(self):
        """Non-excluded categories pass normally."""
        func = self._get_quality_func()
        config = self._make_config()

        trends = [
            _make_scored_trend("테크트렌드", viral=80, category="테크"),
            _make_scored_trend("경제뉴스", viral=75, category="경제"),
            _make_scored_trend("아이돌N", viral=95, category="연예"),
        ]

        result = func(trends, config)
        # tech(80) and economy(75) pass normally, entertainment(95) excluded
        assert len(result) >= 2
        categories = {t.category for t in result}
        assert "연예" not in categories


# ═══════════════════════════════════════════════
#  A-2: Niche-First Scoring
# ═══════════════════════════════════════════════

class TestNicheBonus:
    """Niche category trends get bonus points applied correctly."""

    def test_niche_bonus_applied(self):
        """Tech category gets +10 bonus."""
        from analyzer import _parse_scored_trend_from_dict
        from models import MultiSourceContext
        from config import AppConfig

        config = AppConfig()
        config.niche_categories = ["테크", "경제"]
        config.niche_bonus_points = 10
        config.min_cross_source_confidence = 0  # disable confidence filter

        ctx = MultiSourceContext(
            twitter_insight="X에서 AI 기술 화제",
            reddit_insight="Reddit 활발 토론",
            news_insight="뉴스 기사 다수",
        )

        parsed = {
            "keyword": "AI반도체",
            "viral_potential": 55,
            "category": "테크",
            "trend_acceleration": "+10%",
            "top_insight": "테스트",
            "suggested_angles": [],
            "best_hook_starter": "테스트",
        }

        result = _parse_scored_trend_from_dict(parsed, "AI반도체", 10000, ctx, config)
        # hybrid_viral = 55 * 0.6 + signal * 0.4 + niche_bonus(10)
        assert result.viral_potential > 55 * 0.6, "Niche bonus not applied"

    def test_non_niche_no_bonus(self):
        """Non-niche category gets no bonus."""
        from analyzer import _parse_scored_trend_from_dict
        from models import MultiSourceContext
        from config import AppConfig

        config = AppConfig()
        config.niche_categories = ["테크"]
        config.niche_bonus_points = 10
        config.min_cross_source_confidence = 0

        ctx = MultiSourceContext()
        parsed = {
            "keyword": "아이돌A",
            "viral_potential": 55,
            "category": "연예",
            "trend_acceleration": "+0%",
        }

        result_entertainment = _parse_scored_trend_from_dict(
            parsed, "아이돌A", 0, ctx, config
        )

        parsed2 = {
            "keyword": "AI기술",
            "viral_potential": 55,
            "category": "테크",
            "trend_acceleration": "+0%",
        }
        result_tech = _parse_scored_trend_from_dict(
            parsed2, "AI기술", 0, ctx, config
        )

        # Same viral_potential(55) but tech gets bonus -> tech > entertainment
        assert result_tech.viral_potential > result_entertainment.viral_potential, \
            f"Tech({result_tech.viral_potential}) should > Entertainment({result_entertainment.viral_potential})"

    def test_niche_bonus_respects_cap(self):
        """Bonus does not exceed 100 cap."""
        from analyzer import _parse_scored_trend_from_dict
        from models import MultiSourceContext
        from config import AppConfig

        config = AppConfig()
        config.niche_categories = ["테크"]
        config.niche_bonus_points = 15
        config.min_cross_source_confidence = 0

        ctx = MultiSourceContext(
            twitter_insight="X에서 화제",
            reddit_insight="Reddit 토론",
            news_insight="뉴스 대특집",
        )
        parsed = {
            "keyword": "초강력테크",
            "viral_potential": 98,
            "category": "테크",
            "trend_acceleration": "+50%",
        }

        result = _parse_scored_trend_from_dict(parsed, "초강력테크", 5000000, ctx, config)
        assert result.viral_potential <= 100, f"Exceeds 100 cap: {result.viral_potential}"


# ═══════════════════════════════════════════════
#  A-3: Lazy Context Config Validation
# ═══════════════════════════════════════════════

class TestLazyContext:
    """enable_lazy_context config validation."""

    def test_config_default_enabled(self):
        """Default value: lazy context enabled."""
        from config import AppConfig
        cfg = AppConfig()
        assert cfg.enable_lazy_context is True

    def test_config_from_env_disabled(self, monkeypatch):
        """Env variable can disable lazy context."""
        from config import AppConfig
        monkeypatch.setenv("ENABLE_LAZY_CONTEXT", "false")
        cfg = AppConfig.from_env()
        assert cfg.enable_lazy_context is False

    def test_niche_categories_from_env(self, monkeypatch):
        """Env variable can customize niche categories."""
        from config import AppConfig
        monkeypatch.setenv("NICHE_CATEGORIES", "게임,음식")
        cfg = AppConfig.from_env()
        assert "게임" in cfg.niche_categories
        assert "음식" in cfg.niche_categories

    def test_niche_bonus_from_env(self, monkeypatch):
        """Env variable can set bonus points."""
        from config import AppConfig
        monkeypatch.setenv("NICHE_BONUS_POINTS", "15")
        cfg = AppConfig.from_env()
        assert cfg.niche_bonus_points == 15
