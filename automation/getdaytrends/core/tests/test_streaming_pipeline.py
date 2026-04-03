"""Streaming Pipeline 유닛 테스트."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_mock_trend(name: str, viral: int = 80):
    """Mock RawTrend-like object."""
    t = MagicMock()
    t.name = name
    t.keyword = name
    t.viral_potential = viral
    t.__str__ = lambda self: self.name
    return t


class TestPipelineEvent:
    """PipelineEvent 단위 테스트."""

    def test_default_stage(self):
        from core.streaming_pipeline import PipelineEvent
        ev = PipelineEvent(trend="test")
        assert ev.stage == "queued"
        assert ev.error == ""
        assert ev.elapsed_ms == 0.0

    def test_complete_sets_result(self):
        from core.streaming_pipeline import PipelineEvent
        ev = PipelineEvent(trend="test")
        ev.complete(result="batch_data")
        assert ev.result == "batch_data"
        assert ev.completed_at is not None
        assert ev.elapsed_ms > 0

    def test_complete_with_error(self):
        from core.streaming_pipeline import PipelineEvent
        ev = PipelineEvent(trend="test")
        ev.complete(error="timeout")
        assert ev.error == "timeout"


class TestStreamingPipeline:
    """StreamingPipeline 통합 테스트."""

    @pytest.mark.asyncio
    async def test_basic_flow(self):
        """3개 트렌드가 전체 파이프라인을 통과하는 기본 흐름."""
        from core.streaming_pipeline import StreamingPipeline

        trends = [_make_mock_trend(f"trend_{i}", 80 + i) for i in range(3)]
        contexts = {t.name: MagicMock() for t in trends}

        # Mock functions
        async def mock_score(trend, ctx):
            await asyncio.sleep(0.01)
            return trend  # passthrough

        async def mock_generate(scored):
            await asyncio.sleep(0.01)
            return {"topic": scored.keyword, "tweets": []}

        async def mock_save(trend, batch):
            await asyncio.sleep(0.01)

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn, generator_concurrency=2)
        results = await sp.run(
            trends, contexts,
            score_fn=mock_score,
            generate_fn=mock_generate,
            save_fn=mock_save,
        )

        assert len(results) == 3
        assert sp.success_count == 3
        assert sp.error_count == 0

    @pytest.mark.asyncio
    async def test_no_score_fn_passthrough(self):
        """score_fn이 없으면 트렌드를 그대로 전달."""
        from core.streaming_pipeline import StreamingPipeline

        trends = [_make_mock_trend("test")]
        contexts = {"test": None}

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn, generator_concurrency=1)
        results = await sp.run(trends, contexts)

        assert len(results) == 1
        assert results[0].stage == "saved"

    @pytest.mark.asyncio
    async def test_generator_error_does_not_block(self):
        """Generator 에러가 다른 트렌드 처리를 막지 않음."""
        from core.streaming_pipeline import StreamingPipeline

        trends = [_make_mock_trend(f"t_{i}") for i in range(3)]
        contexts = {t.name: None for t in trends}
        call_count = 0

        async def failing_generate(scored):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("LLM 실패")
            return {"topic": "ok"}

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn, generator_concurrency=1)
        results = await sp.run(
            trends, contexts,
            generate_fn=failing_generate,
        )

        assert len(results) == 3
        errors = [r for r in results if r.error]
        assert len(errors) == 1
        assert sp.error_count == 1

    @pytest.mark.asyncio
    async def test_empty_trends(self):
        """빈 트렌드 리스트에서 정상 종료."""
        from core.streaming_pipeline import StreamingPipeline

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn)
        results = await sp.run([], {})

        assert results == []
        assert sp.error_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_generators(self):
        """여러 Generator Worker가 병렬로 동작."""
        from core.streaming_pipeline import StreamingPipeline

        trends = [_make_mock_trend(f"t_{i}") for i in range(5)]
        contexts = {t.name: None for t in trends}
        gen_timestamps: list[float] = []

        async def timed_generate(scored):
            gen_timestamps.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.05)
            return {"topic": scored.keyword}

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn, generator_concurrency=3)
        results = await sp.run(
            trends, contexts,
            generate_fn=timed_generate,
        )

        assert len(results) == 5
        assert sp.success_count == 5

    @pytest.mark.asyncio
    async def test_save_error_captured(self):
        """Save 에러가 캡처되고 다른 트렌드에 영향 없음."""
        from core.streaming_pipeline import StreamingPipeline

        trends = [_make_mock_trend("t_0"), _make_mock_trend("t_1")]
        contexts = {t.name: None for t in trends}

        async def mock_gen(scored):
            return {"topic": "ok"}

        call_idx = 0
        async def failing_save(trend, batch):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                raise ValueError("DB 저장 실패")

        config = MagicMock()
        conn = MagicMock()

        sp = StreamingPipeline(config, conn, generator_concurrency=1)
        results = await sp.run(
            trends, contexts,
            generate_fn=mock_gen,
            save_fn=failing_save,
        )

        assert len(results) == 2
        errors = [r for r in results if r.error]
        assert len(errors) == 1
        assert "save_error" in errors[0].error


class TestPipelineEventMetrics:
    """PipelineEvent 메트릭 테스트."""

    def test_elapsed_ms_before_completion(self):
        from core.streaming_pipeline import PipelineEvent
        ev = PipelineEvent(trend="test")
        assert ev.elapsed_ms == 0.0

    @pytest.mark.asyncio
    async def test_elapsed_ms_after_completion(self):
        from core.streaming_pipeline import PipelineEvent
        ev = PipelineEvent(trend="test")
        await asyncio.sleep(0.01)
        ev.complete(result="done")
        assert ev.elapsed_ms > 0
