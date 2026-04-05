"""Unit tests for signal_watch pipeline and auto-draft functionality."""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from antigravity_mcp.domain.models import ContentItem
from antigravity_mcp.integrations.signal_scorer import ScoredSignal
from antigravity_mcp.pipelines.signal_watch import _trigger_auto_draft


@pytest.mark.asyncio
async def test_trigger_auto_draft() -> None:
    # 1. Prepare fake actionable signals
    signal1 = ScoredSignal(
        keyword="Quantum Breakthrough",
        composite_score=0.95,
        sources=["reddit", "google_trends"],
        arbitrage_type="early_wave",
        recommended_action="draft_now",
        velocity=0.8,
        category_hint="Tech",
    )
    
    signal2 = ScoredSignal(
        keyword="Mars Colony Update",
        composite_score=0.88,
        sources=["getdaytrends"],
        arbitrage_type="major",
        recommended_action="series",
        velocity=0.5,
        category_hint="Science",
    )

    signals = [signal1, signal2]

    # 2. Mock generate_briefs and PipelineStateStore
    with patch("antigravity_mcp.pipelines.signal_watch.generate_briefs") as mock_generate:
        with patch("antigravity_mcp.pipelines.signal_watch.PipelineStateStore"):
            mock_generate.return_value = ("run_id_123", [], [], "success")

            # 3. Call _trigger_auto_draft
            await _trigger_auto_draft(signals, run_id="test_run_123")

            # 4. Verify generate_briefs was called correctly
            mock_generate.assert_called_once()
            
            kwargs = mock_generate.call_args.kwargs
            items: list[ContentItem] = kwargs["items"]
            
            assert len(items) == 2
            
            # Check mapped fields for signal1
            assert items[0].source_name == "SignalArbitrage"
            assert items[0].category == "TrendAlert"
            assert "Quantum Breakthrough" in items[0].title
            assert "reddit" in items[0].summary
            assert "0.95" in items[0].summary
            
            # Check mapped fields for signal2
            assert items[1].title == "🚀 Trending Alert: Mars Colony Update (major)"
            assert "getdaytrends" in items[1].summary

            assert kwargs["window_name"] == "Trending_Alert"
            assert kwargs["run_id"] == "test_run_123"

@pytest.mark.asyncio
async def test_trigger_auto_draft_empty() -> None:
    # Empty list shouldn't crash
    with patch("antigravity_mcp.pipelines.signal_watch.generate_briefs") as mock_generate:
         with patch("antigravity_mcp.pipelines.signal_watch.PipelineStateStore"):
             mock_generate.return_value = ("run_1", [], [], "success")
             await _trigger_auto_draft([], run_id="test_run_123")
             mock_generate.assert_called_once()
