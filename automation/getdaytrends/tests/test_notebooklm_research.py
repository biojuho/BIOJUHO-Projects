from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _FakeResearchClient:
    def __init__(self):
        self.notebooks = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id="nb_research")))
        self.sources = SimpleNamespace(add_url=AsyncMock(side_effect=[None, RuntimeError("bad source")]))
        self.notes = SimpleNamespace(create=AsyncMock())
        self.chat = SimpleNamespace(
            ask=AsyncMock(
                side_effect=[
                    SimpleNamespace(answer="comparison"),
                    SimpleNamespace(answer="trend"),
                    SimpleNamespace(answer="insights"),
                ]
            )
        )
        self.artifacts = SimpleNamespace(generate_infographic=AsyncMock(return_value=SimpleNamespace(task_id="info_1")))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeNotebookLMClient:
    client = _FakeResearchClient()

    @classmethod
    async def from_storage(cls):
        return cls.client


@pytest.mark.asyncio
async def test_research_tool_sequences_sources_questions_and_infographic(monkeypatch):
    import notebooklm_research

    rpc_types = types.ModuleType("notebooklm.rpc.types")
    rpc_types.InfographicDetail = SimpleNamespace(DETAILED="detailed")
    rpc_types.InfographicOrientation = SimpleNamespace(LANDSCAPE="landscape")
    rpc_types.InfographicStyle = SimpleNamespace(PROFESSIONAL="professional")
    monkeypatch.setitem(sys.modules, "notebooklm.rpc.types", rpc_types)

    fake_client = _FakeResearchClient()
    _FakeNotebookLMClient.client = fake_client
    monkeypatch.setattr(notebooklm_research, "NOTEBOOKLM_AVAILABLE", True)
    monkeypatch.setattr(notebooklm_research, "NotebookLMClient", _FakeNotebookLMClient)

    result = await notebooklm_research.research_tool("AI chips", ["https://a.test", "https://b.test"])

    assert result == {
        "notebook_id": "nb_research",
        "source_count": 1,
        "comparative_analysis": "comparison",
        "data_table": "comparison",
        "trend_summary": "trend",
        "key_insights": "insights",
        "infographic_id": "info_1",
    }
    fake_client.notebooks.create.assert_awaited_once()
    assert fake_client.sources.add_url.await_count == 2
    assert fake_client.chat.ask.await_count == 3
    fake_client.artifacts.generate_infographic.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_bio_company_sequences_analysis_bundle(monkeypatch):
    import notebooklm_research

    rpc_types = types.ModuleType("notebooklm.rpc.types")
    rpc_types.InfographicDetail = SimpleNamespace(DETAILED="detailed")
    rpc_types.InfographicOrientation = SimpleNamespace(PORTRAIT="portrait")
    rpc_types.InfographicStyle = SimpleNamespace(SCIENTIFIC="scientific")
    monkeypatch.setitem(sys.modules, "notebooklm.rpc.types", rpc_types)

    fake_client = _FakeResearchClient()
    fake_client.chat.ask = AsyncMock(
        side_effect=[
            SimpleNamespace(answer="overview"),
            SimpleNamespace(answer="technology"),
            SimpleNamespace(answer="competitive"),
            SimpleNamespace(answer="thesis"),
            SimpleNamespace(answer="tweet"),
        ]
    )
    _FakeNotebookLMClient.client = fake_client
    monkeypatch.setattr(notebooklm_research, "NOTEBOOKLM_AVAILABLE", True)
    monkeypatch.setattr(notebooklm_research, "NotebookLMClient", _FakeNotebookLMClient)

    result = await notebooklm_research.analyze_bio_company("BioCo", ["https://a.test"])

    assert result == {
        "notebook_id": "nb_research",
        "source_count": 1,
        "company_overview": "overview",
        "technology_analysis": "technology",
        "competitive_position": "competitive",
        "investment_thesis": "thesis",
        "tweet_draft": "tweet",
        "infographic_id": "info_1",
    }
    fake_client.notes.create.assert_awaited_once()
    assert fake_client.chat.ask.await_count == 5
