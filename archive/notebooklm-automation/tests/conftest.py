"""Shared test fixtures for notebooklm_automation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_notebooklm_client():
    """Provide a fully mocked NotebookLMClient context manager."""
    mock_client = AsyncMock()

    # notebooks
    mock_nb = MagicMock()
    mock_nb.id = "test-notebook-id-1234"
    mock_client.notebooks.create = AsyncMock(return_value=mock_nb)
    mock_client.notebooks.list = AsyncMock(return_value=[mock_nb])

    # sources
    mock_source = MagicMock()
    mock_source.id = "test-source-id-5678"
    mock_client.sources.add_url = AsyncMock(return_value=mock_source)

    # notes
    mock_client.notes.create = AsyncMock()

    # chat
    mock_answer = MagicMock()
    mock_answer.answer = "테스트 AI 요약 결과입니다."
    mock_client.chat.ask = AsyncMock(return_value=mock_answer)

    # artifacts
    mock_artifact_status = MagicMock()
    mock_artifact_status.artifact_id = "test-artifact-id-9999"
    mock_artifact_status.task_id = "test-task-id-0000"
    mock_client.artifacts.generate_audio = AsyncMock(return_value=mock_artifact_status)
    mock_client.artifacts.generate_infographic = AsyncMock(return_value=mock_artifact_status)
    mock_client.artifacts.generate_report = AsyncMock(return_value=mock_artifact_status)
    mock_client.artifacts.generate_mind_map = AsyncMock(return_value=mock_artifact_status)
    mock_client.artifacts.generate_slide_deck = AsyncMock(return_value=mock_artifact_status)

    # Context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    return mock_client, mock_ctx


@pytest.fixture
def patch_notebooklm(mock_notebooklm_client):
    """Patch NotebookLMClient.from_storage to return the mock client."""
    mock_client, mock_ctx = mock_notebooklm_client
    with (
        patch("notebooklm_automation.bridge.NOTEBOOKLM_AVAILABLE", True),
        patch("notebooklm_automation.bridge.NotebookLMClient") as MockCls,
    ):
        MockCls.from_storage = AsyncMock(return_value=mock_ctx)
        yield mock_client
