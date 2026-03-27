"""Integration tests for XAdapter (tweepy mocked)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from antigravity_mcp.domain.models import ChannelDraft, ContentReport
from antigravity_mcp.integrations.x_adapter import XAdapter


@pytest.fixture
def sample_report():
    return ContentReport(
        report_id="report-test-001",
        category="Tech",
        window_name="morning",
        window_start="2026-03-04T00:00:00+00:00",
        window_end="2026-03-04T07:00:00+00:00",
        summary_lines=["AI breakthrough announced."],
        insights=["Strong industry signals."],
        channel_drafts=[ChannelDraft(channel="x", status="draft", content="Tech brief")],
        asset_status="draft",
        approval_state="manual",
        source_links=["https://example.com/ai"],
        status="draft",
        fingerprint="test-fp-001",
        created_at="2026-03-04T00:00:00+00:00",
        updated_at="2026-03-04T00:00:00+00:00",
    )


def _auto_settings(**overrides):
    attrs = dict(
        auto_push_enabled=True,
        x_daily_post_limit=10,
        content_approval_mode="auto",
        x_api_key="key",
        x_api_secret="secret",
        x_access_token="token",
        x_access_token_secret="token_secret",
        x_bearer_token="",
    )
    attrs.update(overrides)
    return MagicMock(**attrs)


@pytest.mark.asyncio
async def test_publish_manual_mode_returns_draft(sample_report):
    adapter = XAdapter()
    result = await adapter.publish(sample_report, "Test content", approval_mode="manual")
    assert result["status"] == "draft"
    assert "Manual approval" in result.get("message", "")


@pytest.mark.asyncio
async def test_publish_auto_mode_blocked_when_push_disabled(sample_report):
    adapter = XAdapter()
    # default settings have auto_push_enabled=False
    result = await adapter.publish(sample_report, "Test content", approval_mode="auto")
    assert result["status"] == "draft"


@pytest.mark.asyncio
async def test_publish_auto_without_credentials_returns_error(sample_report):
    with patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True), \
         patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=False):
        adapter = XAdapter()
        adapter.settings = _auto_settings()
        result = await adapter.publish(sample_report, "content", approval_mode="auto")
    assert result["status"] == "error"
    assert "credentials" in result["message"].lower()


@pytest.mark.asyncio
async def test_publish_auto_posts_tweet(sample_report):
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = SimpleNamespace(data={"id": "1234567890"})

    with patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True), \
         patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True), \
         patch.object(XAdapter, "_build_client", return_value=mock_client):
        adapter = XAdapter()
        adapter.settings = _auto_settings()
        result = await adapter.publish(sample_report, "Hello X!", approval_mode="auto")

    assert result["status"] == "published"
    assert result["tweet_id"] == "1234567890"
    assert "twitter.com" in result["tweet_url"]
    mock_client.create_tweet.assert_called_once_with(text="Hello X!")


@pytest.mark.asyncio
async def test_publish_truncates_content_to_280(sample_report):
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = SimpleNamespace(data={"id": "999"})

    with patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True), \
         patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True), \
         patch.object(XAdapter, "_build_client", return_value=mock_client):
        adapter = XAdapter()
        adapter.settings = _auto_settings()
        await adapter.publish(sample_report, "A" * 300, approval_mode="auto")

    called_text = mock_client.create_tweet.call_args[1]["text"]
    assert len(called_text) == 280


@pytest.mark.asyncio
async def test_daily_limit_blocks_after_cap(sample_report, tmp_path):
    from antigravity_mcp.state.store import PipelineStateStore

    store = PipelineStateStore(path=tmp_path / "test_x_limit.db")
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = SimpleNamespace(data={"id": "777"})

    with patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True), \
         patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True), \
         patch.object(XAdapter, "_build_client", return_value=mock_client):
        adapter = XAdapter(state_store=store)
        adapter.settings = _auto_settings(x_daily_post_limit=2)

        r1 = await adapter.publish(sample_report, "tweet 1", approval_mode="auto")
        r2 = await adapter.publish(sample_report, "tweet 2", approval_mode="auto")
        r3 = await adapter.publish(sample_report, "tweet 3", approval_mode="auto")

    assert r1["status"] == "published"
    assert r2["status"] == "published"
    assert r3["status"] == "blocked"
    store.close()
