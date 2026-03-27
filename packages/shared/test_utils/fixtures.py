"""Shared test fixtures for DailyNews and getdaytrends."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def make_tmp_state_store(tmp_path: Path):
    """Create a temporary PipelineStateStore for testing."""
    from antigravity_mcp.state.store import PipelineStateStore
    return PipelineStateStore(path=tmp_path / "test.db")


def make_mock_llm_client(response_text: str = '{"summary": ["test"]}'):
    """Create a mock LLM client with a predetermined response."""
    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock.create.return_value = mock_response
    mock.acreate = AsyncMock(return_value=mock_response)
    return mock


def make_sample_articles(count: int = 3, category: str = "Tech") -> list[dict]:
    """Create sample article dicts for testing."""
    return [
        {
            "title": f"Test Article {i}",
            "description": f"Description for test article {i} with enough text for testing.",
            "link": f"https://example.com/article-{i}",
            "source_name": f"Source{i}",
        }
        for i in range(count)
    ]
