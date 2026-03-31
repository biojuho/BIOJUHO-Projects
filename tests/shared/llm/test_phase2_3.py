"""Tests for Phase 2.2 (SmartRouter + ContextMap) and Phase 3 (Trace + MetaOptimizer)."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shared.llm.reasoning.smart_router import (
    QueryComplexity,
    SmartRouter,
    estimate_complexity,
)


# ===========================================================================
# Phase 2.2: SmartRouter + ContextMap integration
# ===========================================================================


class TestSmartRouterContextMapIntegration:
    """Test that SmartRouter correctly injects code context."""

    def test_no_context_map_returns_original_system(self):
        """Without context_map, system prompt is unchanged."""
        client = MagicMock()
        router = SmartRouter(client, context_map=None)
        result = router._inject_code_context(
            "You are an assistant.", "simple query", QueryComplexity.HIGH
        )
        assert result == "You are an assistant."

    def test_low_complexity_skips_injection(self):
        """LOW complexity queries don't get code context."""
        client = MagicMock()
        mock_cmap = MagicMock()
        router = SmartRouter(client, context_map=mock_cmap)

        result = router._inject_code_context(
            "System prompt", "hello", QueryComplexity.LOW
        )
        assert result == "System prompt"
        mock_cmap.get_relevant_context.assert_not_called()

    def test_medium_complexity_injects_context(self):
        """MEDIUM+ complexity queries get code context injected."""
        client = MagicMock()
        mock_cmap = MagicMock()
        mock_cmap.get_relevant_context.return_value = "[Code Context]\n# shared/llm/client.py\nclass LLMClient"
        router = SmartRouter(client, context_map=mock_cmap)

        result = router._inject_code_context(
            "You are an architect.", "SmartRouter 디버깅", QueryComplexity.MEDIUM
        )
        assert "[Code Context]" in result
        assert "You are an architect." in result
        mock_cmap.get_relevant_context.assert_called_once()

    def test_critical_gets_larger_token_budget(self):
        """CRITICAL complexity gets more context tokens."""
        client = MagicMock()
        mock_cmap = MagicMock()
        mock_cmap.get_relevant_context.return_value = "[Code Context]\nbig context"
        router = SmartRouter(client, context_map=mock_cmap)

        router._inject_code_context("sys", "전체 시스템 아키텍처 리팩토링", QueryComplexity.CRITICAL)
        call_kwargs = mock_cmap.get_relevant_context.call_args
        assert call_kwargs.kwargs.get("max_tokens", 0) == 1200

    def test_context_map_error_is_non_fatal(self):
        """If ContextMap raises, system prompt is returned unchanged."""
        client = MagicMock()
        mock_cmap = MagicMock()
        mock_cmap.get_relevant_context.side_effect = RuntimeError("index broken")
        router = SmartRouter(client, context_map=mock_cmap)

        result = router._inject_code_context(
            "You are helpful.", "query", QueryComplexity.HIGH
        )
        assert result == "You are helpful."

    def test_empty_system_prompt_with_context(self):
        """Code context works even with empty system prompt."""
        client = MagicMock()
        mock_cmap = MagicMock()
        mock_cmap.get_relevant_context.return_value = "[Code Context]\nstuff"
        router = SmartRouter(client, context_map=mock_cmap)

        result = router._inject_code_context("", "디버깅", QueryComplexity.HIGH)
        assert result == "[Code Context]\nstuff"


# ===========================================================================
# Phase 3.1: WorkflowTracer
# ===========================================================================


class TestWorkflowTracer:
    """Test workflow trace collection and pattern detection."""

    def test_trace_context_manager(self, tmp_path: Path):
        from shared.telemetry.workflow_trace import WorkflowTracer

        db_path = tmp_path / "test_traces.db"
        tracer = WorkflowTracer(db_path=db_path)

        with tracer.trace("DailyNews", "scoring", model="gemini-2.5-flash") as t:
            t.record(
                prompt_hash=t.hash_prompt("Score this article"),
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                success=True,
            )

        tracer.flush()

        # Verify record was written
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM workflow_traces").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0][1] == "DailyNews"  # pipeline
        assert rows[0][2] == "scoring"  # stage

        tracer.close()

    def test_trace_records_failure(self, tmp_path: Path):
        from shared.telemetry.workflow_trace import WorkflowTracer

        db_path = tmp_path / "test_traces.db"
        tracer = WorkflowTracer(db_path=db_path)

        with pytest.raises(ValueError, match="test error"):
            with tracer.trace("GetDayTrends", "analysis") as t:
                raise ValueError("test error")

        tracer.flush()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT success, error FROM workflow_traces").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0][0] == 0  # success = False
        assert "test error" in rows[0][1]

        tracer.close()

    def test_prompt_hash_consistency(self):
        from shared.telemetry.workflow_trace import TraceContext

        hash1 = TraceContext.hash_prompt("Score this article from 1 to 10")
        hash2 = TraceContext.hash_prompt("Score this article from 1 to 10")
        hash3 = TraceContext.hash_prompt("Summarize this article")

        assert hash1 == hash2  # same prompt → same hash
        assert hash1 != hash3  # different prompt → different hash
        assert len(hash1) == 12  # truncated to 12 chars

    def test_prompt_hash_case_insensitive(self):
        from shared.telemetry.workflow_trace import TraceContext

        hash1 = TraceContext.hash_prompt("Score THIS")
        hash2 = TraceContext.hash_prompt("score this")
        assert hash1 == hash2

    def test_find_repeated_patterns(self, tmp_path: Path):
        from shared.telemetry.workflow_trace import WorkflowTracer

        db_path = tmp_path / "test_patterns.db"
        tracer = WorkflowTracer(db_path=db_path)

        # Insert 6 traces with the same prompt hash
        for i in range(6):
            with tracer.trace("DailyNews", "scoring") as t:
                t.record(
                    prompt_hash="abc123def456",
                    input_tokens=100,
                    output_tokens=50,
                    cost_usd=0.002,
                )

        # Insert 2 traces with a different hash (below threshold)
        for i in range(2):
            with tracer.trace("DailyNews", "analysis") as t:
                t.record(prompt_hash="xyz789", cost_usd=0.001)

        patterns = tracer.find_repeated_patterns(min_count=5, days=1)
        assert len(patterns) == 1
        assert patterns[0].prompt_hash == "abc123def456"
        assert patterns[0].occurrence_count == 6
        assert patterns[0].total_cost_usd > 0

        tracer.close()

    def test_get_stage_summary(self, tmp_path: Path):
        from shared.telemetry.workflow_trace import WorkflowTracer

        db_path = tmp_path / "test_summary.db"
        tracer = WorkflowTracer(db_path=db_path)

        for _ in range(3):
            with tracer.trace("DailyNews", "scoring") as t:
                t.record(cost_usd=0.001)

        with tracer.trace("DailyNews", "analysis") as t:
            t.record(cost_usd=0.005)

        summary = tracer.get_stage_summary("DailyNews", days=1)
        assert len(summary) == 2

        # analysis should be first (higher cost)
        assert summary[0]["stage"] == "analysis"
        assert summary[0]["total_cost_usd"] > 0

        tracer.close()

    def test_buffer_auto_flush(self, tmp_path: Path):
        from shared.telemetry.workflow_trace import WorkflowTracer

        db_path = tmp_path / "test_autoflush.db"
        tracer = WorkflowTracer(db_path=db_path)
        tracer._buffer_size = 3  # small buffer for testing

        for i in range(5):
            with tracer.trace("test", f"stage_{i}") as t:
                t.record(cost_usd=0.001)

        # Should have auto-flushed at least once (at buffer_size=3)
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM workflow_traces").fetchone()[0]
        conn.close()
        assert count >= 3

        tracer.close()


# ===========================================================================
# Phase 3.2: MetaOptimizer
# ===========================================================================


class TestMetaOptimizer:
    """Test AWO-inspired meta-optimization engine."""

    def test_generate_report_empty(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "empty.db")
        optimizer = MetaOptimizer(tracer=tracer)

        report = optimizer.generate_report(days=7)
        assert report.total_traces_analyzed == 0
        assert len(report.suggestions) == 0
        assert report.total_estimated_savings == 0.0

        tracer.close()

    def test_template_conversion_suggestion(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer, OptimizationType
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "patterns.db")

        # Create enough repeated patterns to trigger suggestion
        for _ in range(10):
            with tracer.trace("DailyNews", "scoring") as t:
                t.record(
                    prompt_hash="repeated_hash1",
                    input_tokens=200,
                    output_tokens=100,
                    cost_usd=0.005,
                )

        optimizer = MetaOptimizer(tracer=tracer)
        report = optimizer.generate_report(days=1)

        # Should have at least one template conversion suggestion
        template_suggestions = [
            s for s in report.suggestions
            if s.type == OptimizationType.TEMPLATE_CONVERSION
        ]
        assert len(template_suggestions) >= 1
        assert template_suggestions[0].estimated_savings_usd > 0

        tracer.close()

    def test_report_to_markdown(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "md.db")

        for _ in range(6):
            with tracer.trace("GetDayTrends", "analysis") as t:
                t.record(prompt_hash="md_test_hash", cost_usd=0.003)

        optimizer = MetaOptimizer(tracer=tracer)
        report = optimizer.generate_report(days=1)
        md = report.to_markdown()

        assert "# 🔧 Meta-Optimizer Report" in md
        assert "Estimated savings" in md

        tracer.close()

    def test_report_to_dict(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "dict.db")
        optimizer = MetaOptimizer(tracer=tracer)

        report = optimizer.generate_report(days=1)
        d = report.to_dict()

        assert "generated_at" in d
        assert "total_cost_usd" in d
        assert "suggestions" in d
        assert isinstance(d["suggestions"], list)

        tracer.close()

    def test_save_report(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "save.db")
        optimizer = MetaOptimizer(tracer=tracer)
        report = optimizer.generate_report(days=1)

        output_dir = tmp_path / "reports"
        md_path = optimizer.save_report(report, output_dir=output_dir)

        assert md_path.exists()
        assert md_path.suffix == ".md"
        # JSON counterpart should also exist
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) == 1

        tracer.close()

    def test_high_failure_rate_suggestion(self, tmp_path: Path):
        from shared.llm.meta_optimizer import MetaOptimizer
        from shared.telemetry.workflow_trace import WorkflowTracer

        tracer = WorkflowTracer(db_path=tmp_path / "failures.db")

        # Create a stage with >30% failure rate
        for i in range(10):
            with tracer.trace("BadPipeline", "flaky_stage") as t:
                t.record(
                    prompt_hash="flaky_hash",
                    cost_usd=0.001,
                    success=(i < 5),  # 50% failure rate
                    error="" if i < 5 else "timeout",
                )

        optimizer = MetaOptimizer(tracer=tracer)
        report = optimizer.generate_report(days=1)

        # Should flag the high failure rate
        failure_suggestions = [
            s for s in report.suggestions
            if "실패율" in s.description
        ]
        assert len(failure_suggestions) >= 1

        tracer.close()
