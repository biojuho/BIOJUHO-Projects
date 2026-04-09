"""Unit tests for adapters: skill, x_metrics, metrics pipeline, brain (consolidated)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from antigravity_mcp.state.store import PipelineStateStore

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def state_store(tmp_path):
    store = PipelineStateStore(path=tmp_path / "test_adapters.db")
    yield store
    store.close()


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

    @pytest.mark.asyncio
    async def test_market_snapshot_uses_structured_market_adapter(self, monkeypatch):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        class FakeMarketAdapter:
            def get_snapshot(self, ticker):
                if ticker == "NVDA":
                    return {"ticker": "NVDA", "price": 950.0, "change_pct": 2.5}
                return None

            def get_snapshot_by_keyword(self, keyword):
                if keyword == "Nvidia":
                    return {"ticker": "NVDA", "price": 950.0, "change_pct": 2.5}
                return None

        fake_market_module = SimpleNamespace(MarketAdapter=FakeMarketAdapter)
        monkeypatch.setitem(sys.modules, "antigravity_mcp.integrations.market_adapter", fake_market_module)

        adapter = SkillAdapter()
        result = await adapter.invoke("market_snapshot", {"tickers": ["NVDA"], "keywords": ["Nvidia"]})

        assert result["status"] == "ok"
        snapshots = result["result"]["snapshots"]
        assert snapshots["NVDA"]["price"] == 950.0
        assert snapshots["Nvidia"]["ticker"] == "NVDA"

    @pytest.mark.asyncio
    async def test_brain_analysis_passes_category_and_optional_args(self, monkeypatch):
        from antigravity_mcp.integrations.skill_adapter import SkillAdapter

        captured = {}

        class FakeBrainAdapter:
            async def analyze_news(self, category, articles, time_window="", niche_trends=None):
                captured["category"] = category
                captured["articles"] = articles
                captured["time_window"] = time_window
                captured["niche_trends"] = niche_trends
                return {"summary": "ok"}

        fake_brain_module = SimpleNamespace(BrainAdapter=FakeBrainAdapter)
        monkeypatch.setitem(sys.modules, "antigravity_mcp.integrations.brain_adapter", fake_brain_module)

        adapter = SkillAdapter()
        result = await adapter.invoke(
            "brain_analysis",
            {
                "category": "ai",
                "articles": [{"title": "A", "summary": "B"}],
                "time_window": "24h",
                "niche_trends": [{"keyword": "agents"}],
            },
        )

        assert result["status"] == "ok"
        assert result["result"]["summary"] == "ok"
        assert captured == {
            "category": "ai",
            "articles": [{"title": "A", "summary": "B"}],
            "time_window": "24h",
            "niche_trends": [{"keyword": "agents"}],
        }


class TestEmbeddingAdapter:
    @pytest.mark.asyncio
    async def test_get_embeddings_uses_supported_gemini_endpoint(self, monkeypatch):
        from antigravity_mcp.integrations.embedding_adapter import EmbeddingAdapter

        called = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"embeddings": [{"values": [0.1, 0.2, 0.3]}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, headers=None, json=None):
                called["url"] = url
                called["headers"] = headers
                called["json"] = json
                return FakeResponse()

        monkeypatch.setattr(
            "antigravity_mcp.integrations.embedding_adapter.httpx.AsyncClient",
            FakeAsyncClient,
        )

        adapter = EmbeddingAdapter()
        adapter._api_key = "test-key"
        embeddings = await adapter.get_embeddings(["hello world"])

        assert embeddings == [[0.1, 0.2, 0.3]]
        assert called["url"].endswith("/v1beta/models/gemini-embedding-001:batchEmbedContents")
        assert called["headers"]["x-goog-api-key"] == "test-key"
        assert called["json"]["requests"][0]["model"] == "models/gemini-embedding-001"
        assert called["json"]["requests"][0]["taskType"] == "CLUSTERING"


class TestFactCheckAdapter:
    @pytest.mark.asyncio
    async def test_check_report_excludes_ctas_and_market_lines(self, monkeypatch):
        from antigravity_mcp.integrations.fact_check_adapter import FactCheckAdapter

        captured = {}

        class FakeResult:
            passed = True
            accuracy_score = 1.0
            source_credibility = 1.0
            total_claims = 1
            verified_claims = 1
            hallucinated_claims = 0
            issues = []

        def fake_verify_text_against_sources(text, source_texts, **kwargs):
            captured["text"] = text
            captured["source_texts"] = source_texts
            captured["kwargs"] = kwargs
            return FakeResult()

        monkeypatch.setattr(
            "antigravity_mcp.integrations.fact_check_adapter.resolve_shared_fact_check",
            lambda: (FakeResult, fake_verify_text_against_sources, None),
        )

        adapter = FactCheckAdapter()
        result = await adapter.check_report(
            summary_lines=["## 정보 브리핑", "Bitcoin holds ground as liquidity tightens."],
            insights=[
                "[Market] Bitcoin: $68000",
                "[Continuing] prior theme",
                "**1차 파급 효과:** speculative forecast",
                "**투자자:** 30일 내 재점검",
                "Liquidity stress still matters for exchanges.",
            ],
            drafts_text="Stylized X draft that should not be fact-checked here.",
            source_articles=[
                {"title": "Bitcoin holds ground", "description": "Liquidity tightens", "source_name": "CoinDesk"}
            ],
        )

        assert result["passed"] is True
        assert "Bitcoin holds ground as liquidity tightens." in captured["text"]
        assert "Liquidity stress still matters for exchanges." in captured["text"]
        assert "[Market] Bitcoin: $68000" not in captured["text"]
        assert "**1차 파급 효과:** speculative forecast" not in captured["text"]
        assert "**투자자:** 30일 내 재점검" not in captured["text"]
        assert "Stylized X draft" not in captured["text"]
        assert captured["kwargs"]["min_accuracy"] == 0.45

    @pytest.mark.asyncio
    async def test_check_report_filters_noise_issues(self, monkeypatch):
        from antigravity_mcp.integrations.fact_check_adapter import FactCheckAdapter

        class FakeResult:
            passed = False
            accuracy_score = 0.42
            source_credibility = 0.9
            total_claims = 5
            verified_claims = 2
            hallucinated_claims = 2
            issues = [
                "[Hallucination] entity: '정부'",
                "[Hallucination] entity: 'JSON'",
                "[Hallucination] entity: '프라이버시'",
                "[Unverified number] '6개'",
                "[Hallucination] entity: '교란시'",
                "[Hallucination] entity: 'OpenAI'",
            ]

        monkeypatch.setattr(
            "antigravity_mcp.integrations.fact_check_adapter.resolve_shared_fact_check",
            lambda: (FakeResult, lambda *args, **kwargs: FakeResult(), None),
        )

        adapter = FactCheckAdapter()
        result = await adapter.check_report(
            summary_lines=["OpenAI announced a new model."],
            insights=["OpenAI expanded distribution."],
            drafts_text="",
            source_articles=[{"title": "OpenAI announced a new model", "description": "", "source_name": "Reuters"}],
        )

        assert result["issues"] == ["[Hallucination] entity: 'OpenAI'"]
        assert result["passed"] is False


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
