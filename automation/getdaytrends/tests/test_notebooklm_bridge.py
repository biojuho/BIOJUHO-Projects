from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _FakeNotebookClient:
    def __init__(self):
        self.notebooks = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id="nb_12345678")))
        self.sources = SimpleNamespace(
            add_url=AsyncMock(side_effect=[SimpleNamespace(id="src_1"), RuntimeError("bad url")])
        )
        self.notes = SimpleNamespace(create=AsyncMock())
        self.chat = SimpleNamespace(ask=AsyncMock(return_value=SimpleNamespace(answer="summary text")))
        self.artifacts = SimpleNamespace(
            generate_audio=AsyncMock(return_value=SimpleNamespace(artifact_id="audio_123")),
            generate_report=AsyncMock(return_value=SimpleNamespace(artifact_id="report_123")),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeNotebookLMClient:
    client = _FakeNotebookClient()

    @classmethod
    async def from_storage(cls):
        return cls.client


@pytest.mark.asyncio
async def test_trend_to_notebook_records_sources_context_summary_and_artifacts(tmp_path, monkeypatch):
    import notebooklm_bridge

    fake_client = _FakeNotebookClient()
    _FakeNotebookLMClient.client = fake_client
    monkeypatch.setattr(notebooklm_bridge, "NOTEBOOKLM_AVAILABLE", True)
    monkeypatch.setattr(notebooklm_bridge, "NotebookLMClient", _FakeNotebookLMClient)

    result = await notebooklm_bridge.trend_to_notebook(
        "AI regulation",
        ["https://example.com/one", "https://example.com/two"],
        category="policy",
        context_text="context" * 1000,
        content_types=["audio", "unknown"],
        output_dir=tmp_path / "notebooks",
    )

    assert result["notebook_id"] == "nb_12345678"
    assert result["source_ids"] == ["src_1"]
    assert result["summary"] == "summary text"
    assert result["artifacts"] == {"audio": "audio_123"}
    assert (tmp_path / "notebooks").exists()
    fake_client.notebooks.create.assert_awaited_once()
    fake_client.notes.create.assert_awaited_once()
    assert len(fake_client.notes.create.await_args.kwargs["content"]) == 5000
    fake_client.chat.ask.assert_awaited_once()


@pytest.mark.asyncio
async def test_trend_to_notebook_rejects_missing_notebooklm(monkeypatch):
    import notebooklm_bridge

    monkeypatch.setattr(notebooklm_bridge, "NOTEBOOKLM_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="notebooklm-py"):
        await notebooklm_bridge.trend_to_notebook("AI regulation", [])


@pytest.mark.asyncio
async def test_generate_content_dispatches_standard_artifacts():
    import notebooklm_bridge

    fake_client = _FakeNotebookClient()

    assert await notebooklm_bridge._generate_content(fake_client, "nb_1", "AI", "audio", "voice notes") == "audio_123"
    assert await notebooklm_bridge._generate_content(fake_client, "nb_1", "AI", "report", "") == "report_123"
    assert await notebooklm_bridge._generate_content(fake_client, "nb_1", "AI", "unknown", "") is None
    fake_client.artifacts.generate_audio.assert_awaited_once_with("nb_1", instructions="voice notes")
    fake_client.artifacts.generate_report.assert_awaited_once_with("nb_1", report_format="briefing-doc")


@pytest.mark.asyncio
async def test_content_factory_sequences_notebook_steps(monkeypatch):
    import notebooklm_bridge

    fake_client = _FakeNotebookClient()
    fake_client.chat.ask = AsyncMock(
        side_effect=[
            SimpleNamespace(answer="factory summary"),
            SimpleNamespace(answer="factory tweet "),
        ]
    )
    _FakeNotebookLMClient.client = fake_client
    monkeypatch.setattr(notebooklm_bridge, "NOTEBOOKLM_AVAILABLE", True)
    monkeypatch.setattr(notebooklm_bridge, "NotebookLMClient", _FakeNotebookLMClient)
    monkeypatch.setattr(
        notebooklm_bridge,
        "_generate_content_factory_outputs",
        AsyncMock(return_value={"infographic_id": "info_123", "report_id": "report_123"}),
    )

    result = await notebooklm_bridge.content_factory(
        "AI regulation",
        ["https://example.com/one", "https://example.com/two"],
        category="policy",
        context_text="context body",
    )

    assert result == {
        "notebook_id": "nb_12345678",
        "source_count": 1,
        "summary": "factory summary",
        "tweet_draft": "factory tweet",
        "infographic_id": "info_123",
        "report_id": "report_123",
    }
    fake_client.notebooks.create.assert_awaited_once()
    fake_client.notes.create.assert_awaited_once()
    assert fake_client.chat.ask.await_count == 2


@pytest.mark.asyncio
async def test_enrich_trends_with_notebooklm_filters_and_converts(monkeypatch):
    import notebooklm_bridge

    class _Context:
        sources = [{"url": "https://example.com/context"}]

        def to_combined_text(self):
            return "combined context"

    trends = [
        SimpleNamespace(keyword="low", viral_potential=50, category="policy"),
        SimpleNamespace(keyword="high", viral_potential=91, category="policy"),
    ]

    mock_convert = AsyncMock(return_value={"keyword": "high", "notebook_id": "nb_1"})
    monkeypatch.setattr(notebooklm_bridge, "NOTEBOOKLM_AVAILABLE", True)
    monkeypatch.setattr(notebooklm_bridge, "trend_to_notebook", mock_convert)

    result = await notebooklm_bridge.enrich_trends_with_notebooklm(
        trends,
        {"high": _Context()},
        min_viral_score=80,
        content_types=["audio"],
    )

    assert result == [{"keyword": "high", "notebook_id": "nb_1"}]
    mock_convert.assert_awaited_once_with(
        keyword="high",
        urls=["https://example.com/context"],
        viral_score=91,
        category="policy",
        context_text="combined context",
        content_types=["audio"],
    )
