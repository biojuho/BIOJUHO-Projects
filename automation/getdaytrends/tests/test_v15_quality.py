# -*- coding: utf-8 -*-
"""
v15.0 Phase B Tests
  B-1: QA metrics tracking
  B-2: Content diversity (template/persona rotation)
  B-3: Named persona rotation
"""
import pytest


from models import MultiSourceContext, ScoredTrend


def _make_trend(
    keyword: str = "테스트",
    category: str = "테크",
    viral: int = 80,
) -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral,
        category=category,
        context=MultiSourceContext(),
    )


# ═══════════════════════════════════════════════
#  B-1: QA Metrics Tracking (DB)
# ═══════════════════════════════════════════════

class TestQAMetrics:
    """get_qa_summary DB metrics function tests."""

    @pytest.mark.asyncio
    async def test_empty_db_returns_zeros(self, memory_db):
        from db import get_qa_summary
        result = await get_qa_summary(memory_db, days=7)
        assert result["total_feedbacks"] == 0
        assert result["avg_qa_score"] == 0.0
        assert result["regeneration_rate"] == 0.0
        assert result["by_category"] == {}
        assert result["recent_scores"] == []

    @pytest.mark.asyncio
    async def test_single_feedback(self, memory_db):
        from db import get_qa_summary, record_content_feedback
        await record_content_feedback(
            memory_db, keyword="AI뉴스", category="테크",
            qa_score=85.0, regenerated=False,
        )
        result = await get_qa_summary(memory_db, days=7)
        assert result["total_feedbacks"] == 1
        assert result["avg_qa_score"] == 85.0
        assert result["regeneration_rate"] == 0.0
        assert "테크" in result["by_category"]

    @pytest.mark.asyncio
    async def test_regeneration_rate(self, memory_db):
        from db import get_qa_summary, record_content_feedback
        # 3 total, 1 regenerated -> rate = 1/3 = 0.333
        await record_content_feedback(memory_db, keyword="A", qa_score=80)
        await record_content_feedback(memory_db, keyword="B", qa_score=40, regenerated=True)
        await record_content_feedback(memory_db, keyword="C", qa_score=70)

        result = await get_qa_summary(memory_db, days=7)
        assert result["total_feedbacks"] == 3
        assert 0.33 <= result["regeneration_rate"] <= 0.34

    @pytest.mark.asyncio
    async def test_category_breakdown(self, memory_db):
        from db import get_qa_summary, record_content_feedback
        await record_content_feedback(memory_db, keyword="테크1", category="테크", qa_score=90)
        await record_content_feedback(memory_db, keyword="테크2", category="테크", qa_score=80)
        await record_content_feedback(memory_db, keyword="연예1", category="연예", qa_score=60)

        result = await get_qa_summary(memory_db, days=7)
        assert "테크" in result["by_category"]
        assert result["by_category"]["테크"]["count"] == 2
        assert "연예" in result["by_category"]


# ═══════════════════════════════════════════════
#  B-2: Content Diversity Config
# ═══════════════════════════════════════════════

class TestDiversityConfig:
    """diversity_sim_threshold config basic validation + env loading."""

    def test_default_threshold(self):
        from config import AppConfig
        cfg = AppConfig()
        assert cfg.diversity_sim_threshold == 0.85

    def test_threshold_from_env(self, monkeypatch):
        from config import AppConfig
        monkeypatch.setenv("DIVERSITY_SIM_THRESHOLD", "0.92")
        cfg = AppConfig.from_env()
        assert cfg.diversity_sim_threshold == 0.92

    @pytest.mark.asyncio
    async def test_content_hashes_empty(self, memory_db):
        from db import get_content_hashes
        hashes = await get_content_hashes(memory_db, hours=24)
        assert hashes == set()


# ═══════════════════════════════════════════════
#  B-3: Named Persona Rotation
# ═══════════════════════════════════════════════

class TestPersonaRotation:
    """Category/day-of-week persona selection mode test."""

    def _make_config(self, **kw):
        from config import AppConfig
        cfg = AppConfig()
        cfg.tone = "joongyeon"
        cfg.persona_rotation = kw.get("mode", "category")
        cfg.persona_pool = kw.get("pool", ["joongyeon", "analyst", "storyteller"])
        return cfg

    def test_category_mode_tech(self):
        from generator import select_persona
        cfg = self._make_config(mode="category")
        trend = _make_trend(keyword="AI기술", category="테크")
        assert select_persona(trend, cfg) == "joongyeon"

    def test_category_mode_economy(self):
        from generator import select_persona
        cfg = self._make_config(mode="category")
        trend = _make_trend(keyword="금리인상", category="경제")
        assert select_persona(trend, cfg) == "analyst"

    def test_category_mode_society(self):
        from generator import select_persona
        cfg = self._make_config(mode="category")
        trend = _make_trend(keyword="사회이슈", category="사회")
        assert select_persona(trend, cfg) == "storyteller"

    def test_round_robin_mode(self):
        from generator import select_persona, _round_robin_counter
        import generator
        generator._round_robin_counter = 0

        cfg = self._make_config(mode="round_robin")
        trends = [
            _make_trend(keyword="A", category="테크"),
            _make_trend(keyword="B", category="테크"),
            _make_trend(keyword="C", category="테크"),
        ]
        results = [select_persona(t, cfg) for t in trends]
        assert results == ["joongyeon", "analyst", "storyteller"]

    def test_fixed_mode(self):
        from generator import select_persona
        cfg = self._make_config(mode="fixed")
        trend = _make_trend(keyword="아무거나", category="정치")
        assert select_persona(trend, cfg) == "joongyeon"  # config.tone

    def test_empty_pool_returns_tone(self):
        from generator import select_persona
        cfg = self._make_config(mode="category", pool=[])
        trend = _make_trend(keyword="테스트", category="테크")
        assert select_persona(trend, cfg) == "joongyeon"  # config.tone

    def test_persona_config_from_env(self, monkeypatch):
        from config import AppConfig
        monkeypatch.setenv("PERSONA_ROTATION", "round_robin")
        monkeypatch.setenv("PERSONA_POOL", "analyst,creative")
        cfg = AppConfig.from_env()
        assert cfg.persona_rotation == "round_robin"
        assert cfg.persona_pool == ["analyst", "creative"]

    def test_unknown_category_uses_first_pool(self):
        from generator import select_persona
        cfg = self._make_config(mode="category")
        trend = _make_trend(keyword="특수음악", category="미분류")
        # Unknown category -> pool[0]
        assert select_persona(trend, cfg) == "joongyeon"
