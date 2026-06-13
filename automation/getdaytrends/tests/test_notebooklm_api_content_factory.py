from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


def _factory_result() -> dict:
    return {
        "notebook_id": "nb_123",
        "source_count": 2,
        "summary": "summary",
        "tweet_draft": "draft tweet",
        "infographic_id": "info_123",
        "report_id": "report_123",
    }


@pytest.mark.asyncio
async def test_content_factory_auto_discovers_sources_and_publishes_optional_outputs():
    from notebooklm_api import ContentFactoryRequest, run_content_factory

    with (
        patch("notebooklm_api.NOTEBOOKLM_AVAILABLE", True),
        patch("notebooklm_api.content_factory", new_callable=AsyncMock, return_value=_factory_result()) as mock_factory,
        patch(
            "notebooklm_api.auto_discover_sources",
            new_callable=AsyncMock,
            return_value=[{"url": "https://example.com/a"}, {"url": "https://example.com/b"}],
        ) as mock_discover,
        patch(
            "notebooklm_api.publish_to_notion",
            new_callable=AsyncMock,
            return_value={"notion_url": "https://notion.so/page"},
        ) as mock_notion,
        patch("notebooklm_api.post_tweet", new_callable=AsyncMock, return_value={"ok": True, "tweet_id": "42"}) as mock_x,
    ):
        result = await run_content_factory(
            ContentFactoryRequest(
                keyword="AI regulation",
                category="policy",
                notion_api_key="notion-key",
                notion_database_id="db",
                x_access_token="x-token",
            )
        )

    assert result["notebook_id"] == "nb_123"
    assert result["notion_url"] == "https://notion.so/page"
    assert result["tweet_url"] == "https://x.com/i/status/42"
    mock_discover.assert_awaited_once_with("AI regulation", max_total=8)
    mock_factory.assert_awaited_once_with(
        keyword="AI regulation",
        urls=["https://example.com/a", "https://example.com/b"],
        category="policy",
        context_text="",
    )
    mock_notion.assert_awaited_once()
    mock_x.assert_awaited_once_with(text="draft tweet", access_token="x-token")


@pytest.mark.asyncio
async def test_content_factory_unavailable_returns_503():
    from notebooklm_api import ContentFactoryRequest, run_content_factory

    with patch("notebooklm_api.NOTEBOOKLM_AVAILABLE", False):
        with pytest.raises(HTTPException) as exc_info:
            await run_content_factory(ContentFactoryRequest(keyword="AI regulation"))

    assert exc_info.value.status_code == 503
