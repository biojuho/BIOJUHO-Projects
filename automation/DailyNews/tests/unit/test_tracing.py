"""Tests for trace context propagation."""

from __future__ import annotations

from antigravity_mcp.tracing import current_trace_id, trace_context


class TestTraceContext:
    def test_default_empty(self):
        assert current_trace_id() == ""

    def test_sets_and_restores(self):
        assert current_trace_id() == ""
        with trace_context("run-123"):
            assert current_trace_id() == "run-123"
        assert current_trace_id() == ""

    def test_nesting(self):
        with trace_context("outer"):
            assert current_trace_id() == "outer"
            with trace_context("inner"):
                assert current_trace_id() == "inner"
            assert current_trace_id() == "outer"
        assert current_trace_id() == ""

    def test_restores_on_exception(self):
        try:
            with trace_context("will-fail"):
                assert current_trace_id() == "will-fail"
                raise ValueError("boom")
        except ValueError:
            pass
        assert current_trace_id() == ""
