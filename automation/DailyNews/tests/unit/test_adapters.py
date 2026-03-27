"""Unit tests for adapters: skill, x_metrics, metrics pipeline, brain (consolidated)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_mcp.state.store import PipelineStateStore


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def state_store(tmp_path):
    return PipelineStateStore(path=tmp_path / "test_adapters.db")


# ─── SkillAdapter ─────────────────────────────────────────────────────────────

class TestSkillAdapter:
    def test_list_skills_has_builtins(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        skills = adapter.list_skills()
        assert "market_snapshot" in skills
        assert "sentiment_classify" in skills
        assert "proofread" in skills
        assert "brain_analysis" in skills
        assert "summarize_category" in skills
        assert len(skills) == 5

    @pytest.mark.asyncio
    async def test_invoke_unknown_skill(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        result = await adapter.invoke("nonexistent_skill", {})
        assert result["status"] == "error"
        assert "Unknown skill" in result["message"]

    @pytest.mark.asyncio
    async def test_invoke_proofread_missing_text(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()
        result = await adapter.invoke("proofread", {})
        assert result["status"] == "error"

    def test_register_custom_skill(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()

        async def my_skill(params):
            return {"hello": "world"}

        adapter.register("my_custom", my_skill)
        assert "my_custom" in adapter.list_skills()

    @pytest.mark.asyncio
    async def test_invoke_custom_skill(self):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        adapter = SkillAdapter()

        async def echo_skill(params):
            return {"echo": params.get("msg", "")}

        adapter.register("echo", echo_skill)
        result = await adapter.invoke("echo", {"msg": "test"})
        assert result["status"] == "ok"
        assert result["result"]["echo"] == "test"


# ─── XMetricsAdapter ─────────────────────────────────────────────────────────

class TestXMetricsAdapter:
    def test_unavailable_without_bearer(self):
        from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter

        with patch.dict("os.environ", {}, clear=False):
            adapter = XMetricsAdapter()
            # It should not crash; availability depends on config
            assert isinstance(adapter.is_available, bool)

    @pytest.mark.asyncio
    async def test_fetch_metrics_no_token_returns_empty(self):
        from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter

        adapter = XMetricsAdapter()
        adapter._bearer_token = None
        result = await adapter.fetch_metrics(["123", "456"])
        assert result == []

    @pytest.mark.asyncio
    async def test_collect_and_store_no_state_store(self):
        from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter

        adapter = XMetricsAdapter(state_store=None)
        adapter._bearer_token = "fake"
        count = await adapter.collect_and_store(["123"])
        assert count == 0

    @pytest.mark.asyncio
    async def test_collect_and_store_success(self, state_store):
        from antigravity_mcp.integrations.x_metrics_adapter import XMetricsAdapter

        adapter = XMetricsAdapter(state_store=state_store)
        adapter._bearer_token = "fake"
        mock_metrics = [
            {
                "tweet_id": "111",
                "text": "test tweet",
                "created_at": "2026-03-19T00:00:00Z",
                "impressions": 100,
                "likes": 10,
                "retweets": 5,
                "replies": 2,
                "quotes": 1,
                "bookmarks": 3,
            }
        ]
        adapter.fetch_metrics = AsyncMock(return_value=mock_metrics)
        count = await adapter.collect_and_store(["111"], report_id="rpt-001")
        assert count == 1
        stored = state_store.get_tweet_metrics("111")
        assert stored is not None
        assert stored["impressions"] == 100
        assert stored["report_id"] == "rpt-001"


# ─── Metrics Pipeline ────────────────────────────────────────────────────────

class TestMetricsPipeline:
    @pytest.mark.asyncio
    async def test_collect_recent_no_tweets(self, state_store):
        from antigravity_mcp.pipelines.metrics import collect_recent_metrics

        run_id, count, warnings = await collect_recent_metrics(state_store=state_store)
        assert count == 0
        assert warnings == []

    @pytest.mark.asyncio
    async def test_collect_recent_with_tweets(self, state_store):
        from antigravity_mcp.pipelines.metrics import collect_recent_metrics

        state_store.record_published_tweet_id("rpt-001", "tweet-abc", "preview text")
        with patch("antigravity_mcp.pipelines.metrics.XMetricsAdapter") as MockAdapter:
            mock_instance = MockAdapter.return_value
            mock_instance.is_available = True
            mock_instance.collect_and_store = AsyncMock(return_value=1)
            run_id, count, warnings = await collect_recent_metrics(state_store=state_store)
            assert count == 1


# ─── State Store Metrics Mixin ────────────────────────────────────────────────

class TestMetricsMixin:
    def test_record_and_get_recent_tweet_ids(self, state_store):
        state_store.record_published_tweet_id("rpt-1", "tweet-001", "content preview")
        state_store.record_published_tweet_id("rpt-1", "tweet-002")
        ids = state_store.get_recent_tweet_ids(hours=1)
        assert "tweet-001" in ids
        assert "tweet-002" in ids

    def test_get_metrics_summary_empty(self, state_store):
        summary = state_store.get_metrics_summary(days=7)
        assert summary["total_tweets"] == 0

    def test_upsert_and_get_tweet_metrics(self, state_store):
        state_store.upsert_tweet_metrics(
            tweet_id="t-100",
            report_id="rpt-x",
            impressions=500,
            likes=50,
            retweets=10,
        )
        m = state_store.get_tweet_metrics("t-100")
        assert m is not None
        assert m["impressions"] == 500
        # Update
        state_store.upsert_tweet_metrics(tweet_id="t-100", impressions=600, likes=55)
        m2 = state_store.get_tweet_metrics("t-100")
        assert m2["impressions"] == 600

    def test_get_top_tweets(self, state_store):
        state_store.upsert_tweet_metrics(tweet_id="a", impressions=100)
        state_store.upsert_tweet_metrics(tweet_id="b", impressions=300)
        state_store.upsert_tweet_metrics(tweet_id="c", impressions=200)
        top = state_store.get_top_tweets(days=1, limit=2, sort_by="impressions")
        assert len(top) == 2
        assert top[0]["tweet_id"] == "b"


# ─── BrainAdapter ─────────────────────────────────────────────────────────────

class TestBrainAdapter:
    def test_category_hints_present(self):
        from antigravity_mcp.integrations.brain_adapter import _CATEGORY_PROMPT_HINTS

        assert "Tech" in _CATEGORY_PROMPT_HINTS
        assert "Economy_KR" in _CATEGORY_PROMPT_HINTS
        assert "Crypto" in _CATEGORY_PROMPT_HINTS
        assert "AI_Deep" in _CATEGORY_PROMPT_HINTS
        for hints in _CATEGORY_PROMPT_HINTS.values():
            assert "role" in hints
            assert "focus" in hints
            assert "tone" in hints

    def test_robust_json_parse(self):
        from antigravity_mcp.integrations.brain_adapter import _robust_json_parse

        assert _robust_json_parse('{"a": 1}') == {"a": 1}
        assert _robust_json_parse('```json\n{"b": 2}\n```') == {"b": 2}
        assert _robust_json_parse('{"c": 3,}') == {"c": 3}
        assert _robust_json_parse("not json") is None

    @pytest.mark.asyncio
    async def test_analyze_news_no_client(self):
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        adapter = BrainAdapter()
        adapter._client = None
        result = await adapter.analyze_news("Tech", [{"title": "test", "description": "desc"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_news_empty_articles(self):
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        adapter = BrainAdapter()
        result = await adapter.analyze_news("Tech", [])
        assert result is None
