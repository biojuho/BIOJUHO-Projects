"""Tests for LangGraph coordination layer.

Covers:
  - PipelineState initialization
  - ContentPipelineGraph default nodes
  - Conditional retry logic
  - Custom node overrides
  - Graph build (requires langgraph)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from shared.harness.constitution import Constitution
from shared.harness.adapters.native import NativeHarnessAdapter
from shared.harness.coordination.graph import (
    ContentPipelineGraph,
    PipelineState,
    build_content_pipeline,
    LANGGRAPH_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_constitution() -> Constitution:
    return Constitution.from_dict({
        "agent_name": "test-pipeline",
        "max_budget_usd": 2.0,
        "tools": [
            {"name": "llm_call", "allowed": True, "max_calls": 200},
            {"name": "web_search", "allowed": True, "max_calls": 50},
        ],
    })


def _make_adapter() -> NativeHarnessAdapter:
    async def executor(tool_name, tool_input):
        return {"tool": tool_name, "generated": "테스트 콘텐츠"}
    return NativeHarnessAdapter(_make_constitution(), tool_executor=executor)


# ===========================================================================
# Test: PipelineState
# ===========================================================================

class TestPipelineState:
    def test_initial_state(self):
        state = PipelineState.initial(["trend1", "trend2"])
        assert state["trends_input"] == ["trend1", "trend2"]
        assert state["collected"] == []
        assert state["retry_count"] == 0
        assert state["approved"] is False
        assert state["max_retries"] == 2

    def test_is_dict_subclass(self):
        state = PipelineState.initial()
        assert isinstance(state, dict)

    def test_empty_initial(self):
        state = PipelineState.initial()
        assert state["trends_input"] is None


# ===========================================================================
# Test: ContentPipelineGraph — Default nodes
# ===========================================================================

class TestContentPipelineGraphDefaults:
    @pytest.fixture
    def graph(self):
        return ContentPipelineGraph(adapter=_make_adapter())

    @pytest.mark.asyncio
    async def test_default_collect(self, graph):
        state = PipelineState.initial([{"topic": "AI"}])
        result = await graph._default_collect(state)
        assert result["collected"] == [{"topic": "AI"}]
        assert len(result["trace"]) == 1
        assert result["trace"][0]["step"] == "collect"

    @pytest.mark.asyncio
    async def test_default_analyze(self, graph):
        state = PipelineState.initial()
        state["collected"] = [{"topic": "AI"}, {"topic": "ML"}]
        result = await graph._default_analyze(state)
        assert len(result["scored"]) == 2
        assert all("score" in item for item in result["scored"])

    @pytest.mark.asyncio
    async def test_default_analyze_with_existing_scores(self, graph):
        state = PipelineState.initial()
        state["collected"] = [{"topic": "AI", "score": 9.0}]
        result = await graph._default_analyze(state)
        assert result["scored"][0]["score"] == 9.0

    @pytest.mark.asyncio
    async def test_default_qa_approves_good_content(self, graph):
        state = PipelineState.initial()
        state["generated"] = [
            {"content": "좋은 콘텐츠", "success": True},
            {"content": "더 좋은 콘텐츠", "success": True},
        ]
        result = await graph._default_qa(state)
        assert result["approved"] is True
        assert len(result["qa_results"]) == 2

    @pytest.mark.asyncio
    async def test_default_qa_rejects_failed_content(self, graph):
        state = PipelineState.initial()
        state["generated"] = [
            {"content": None, "success": False},
        ]
        result = await graph._default_qa(state)
        assert result["approved"] is False

    @pytest.mark.asyncio
    async def test_default_publish(self, graph):
        state = PipelineState.initial()
        state["qa_results"] = [
            {"item": {"content": "x"}, "passed": True, "score": 8.0},
        ]
        result = await graph._default_publish(state)
        assert any(t["step"] == "publish" for t in result["trace"])


# ===========================================================================
# Test: Retry logic
# ===========================================================================

class TestRetryLogic:
    @pytest.fixture
    def graph(self):
        return ContentPipelineGraph(adapter=_make_adapter())

    def test_approved_goes_to_publish(self, graph):
        state = PipelineState.initial()
        state["approved"] = True
        assert graph._should_retry(state) == "publish"

    def test_not_approved_retries(self, graph):
        state = PipelineState.initial()
        state["approved"] = False
        state["retry_count"] = 0
        state["max_retries"] = 2
        assert graph._should_retry(state) == "regenerate"

    def test_exhausted_retries_publishes(self, graph):
        state = PipelineState.initial()
        state["approved"] = False
        state["retry_count"] = 2
        state["max_retries"] = 2
        assert graph._should_retry(state) == "publish"

    @pytest.mark.asyncio
    async def test_retry_gate_increments(self, graph):
        state = PipelineState.initial()
        state["retry_count"] = 0
        result = await graph._retry_gate(state)
        assert result["retry_count"] == 1

    def test_custom_qa_threshold(self):
        graph = ContentPipelineGraph(
            adapter=_make_adapter(),
            qa_threshold=9.0,
        )
        assert graph.qa_threshold == 9.0


# ===========================================================================
# Test: Custom node overrides
# ===========================================================================

class TestCustomOverrides:
    @pytest.mark.asyncio
    async def test_custom_collect(self):
        async def my_collect(state):
            state["collected"] = [{"custom": True}]
            return state

        graph = ContentPipelineGraph(
            adapter=_make_adapter(),
            collect_fn=my_collect,
        )
        state = PipelineState.initial()
        result = await graph.collect_fn(state)
        assert result["collected"] == [{"custom": True}]

    @pytest.mark.asyncio
    async def test_custom_qa(self):
        async def strict_qa(state):
            state["qa_results"] = [{"passed": False, "score": 3.0}]
            state["approved"] = False
            return state

        graph = ContentPipelineGraph(
            adapter=_make_adapter(),
            qa_fn=strict_qa,
        )
        state = PipelineState.initial()
        state["generated"] = [{"content": "test", "success": True}]
        result = await graph.qa_fn(state)
        assert not result["approved"]


# ===========================================================================
# Test: build_content_pipeline factory
# ===========================================================================

class TestBuildContentPipeline:
    def test_factory_creates_graph(self):
        constitution = _make_constitution()
        pipeline = build_content_pipeline(constitution)
        assert isinstance(pipeline, ContentPipelineGraph)
        assert pipeline.qa_threshold == 7.0

    def test_factory_with_custom_threshold(self):
        constitution = _make_constitution()
        pipeline = build_content_pipeline(constitution, qa_threshold=8.5)
        assert pipeline.qa_threshold == 8.5

    def test_factory_with_custom_fns(self):
        async def my_gen(state):
            return state

        constitution = _make_constitution()
        pipeline = build_content_pipeline(constitution, generate_fn=my_gen)
        assert pipeline.generate_fn is my_gen


# ===========================================================================
# Test: Full graph build (requires langgraph)
# ===========================================================================

@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="langgraph not installed")
class TestGraphBuild:
    def test_build_compiles(self):
        constitution = _make_constitution()
        pipeline = build_content_pipeline(constitution)
        compiled = pipeline.build()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_full_run(self):
        constitution = _make_constitution()
        pipeline = build_content_pipeline(constitution)
        result = await pipeline.run(
            PipelineState.initial([{"topic": "테스트 트렌드"}])
        )
        assert isinstance(result, PipelineState)
        assert len(result["trace"]) > 0
        # Should have at least collect + analyze + generate + qa + publish
        steps = [t["step"] for t in result["trace"]]
        assert "collect" in steps
        assert "analyze" in steps
