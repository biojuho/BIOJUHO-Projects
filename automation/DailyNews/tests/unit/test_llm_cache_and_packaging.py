from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentItem, ContentReport
from antigravity_mcp.integrations import llm_adapter as llm_module
from antigravity_mcp.pipelines.collect import collect_content_items
from antigravity_mcp.pipelines.publish import publish_report
from antigravity_mcp.state.store import PipelineStateStore


class FakePolicy:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_llm_adapter_reuses_persistent_cache(monkeypatch, tmp_path):
    store = PipelineStateStore(tmp_path / "pipeline_state.db")
    fake_response = SimpleNamespace(
        text="Summary\n- First line\nInsights\n- First insight\nDraft\n- Draft post",
        model_name="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
    )
    fake_client = SimpleNamespace(generate_with_policy=AsyncMock(return_value=fake_response))

    adapter = llm_module.LLMAdapter(state_store=store)
    adapter._client._llm_client = fake_client
    adapter._client._task_tier = "medium"
    adapter._client._policy_cls = FakePolicy
    items = [
        ContentItem(
            source_name="Feed",
            category="Tech",
            title="Story A",
            link="https://example.com/story-a",
            summary="Summary A",
        )
    ]

    payload_1, warnings_1 = await adapter.build_report_payload(
        category="Tech",
        items=items,
        window_name="manual",
    )
    payload_2, warnings_2 = await adapter.build_report_payload(
        category="Tech",
        items=items,
        window_name="manual",
    )

    assert warnings_1 == []
    assert warnings_2 == []
    assert fake_client.generate_with_policy.await_count == 1
    assert fake_client.generate_with_policy.await_args.kwargs["policy"].kwargs["tier"] == "medium"
    assert payload_1[0] == payload_2[0]
    assert payload_2[2][0].channel == "x"
    assert payload_2[2][1].channel == "canva"

    stats = store.get_token_usage_stats(hours=24)
    assert stats["call_count"] == 1
    assert stats["cache_hit_count"] == 1
    assert stats["estimated_cost_usd"] == pytest.approx(0.00045, rel=1e-6)
    assert stats["estimated_cost_avoided_usd"] == pytest.approx(0.00045, rel=1e-6)



@pytest.mark.asyncio
async def test_collect_default_feed_adapter_receives_state_store(monkeypatch, tmp_path):
    store = PipelineStateStore(tmp_path / "pipeline_state.db")
    captured: dict[str, object] = {}

    class FakeFeedAdapter:
        def __init__(self, *, state_store=None):
            captured["state_store"] = state_store

        async def fetch_entries(self, url: str):
            return []

    monkeypatch.setattr("antigravity_mcp.integrations.feed_adapter.FeedAdapter", FakeFeedAdapter)
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.load_sources",
        lambda: {"Tech": [{"name": "Feed", "url": "https://example.com/rss"}]},
    )

    items, warnings = await collect_content_items(
        categories=["Tech"],
        window_name="manual",
        max_items=5,
        state_store=store,
    )

    assert items == []
    assert warnings == []
    assert captured["state_store"] is store


@pytest.mark.asyncio
async def test_publish_forces_manual_approval_when_policy_requires_it(monkeypatch, tmp_path):
    from antigravity_mcp.config import get_settings

    store = PipelineStateStore(tmp_path / "pipeline_state.db")
    report = ContentReport(
        report_id="report-1",
        category="Tech",
        window_name="manual",
        window_start="2026-03-04T00:00:00+00:00",
        window_end="2026-03-04T12:00:00+00:00",
        summary_lines=["line 1", "line 2"],
        insights=["insight 1"],
        channel_drafts=[ChannelDraft(channel="x", status="draft", content="Draft post")],
        source_links=["https://example.com/story-a"],
        fingerprint="fp-1",
    )
    store.save_report(report)

    class FakeNotion:
        def is_configured(self) -> bool:
            return False

    class FakeX:
        def __init__(self) -> None:
            self.approval_modes: list[str] = []

        async def publish(self, report, content: str, *, approval_mode: str):
            self.approval_modes.append(approval_mode)
            return {"status": "draft", "message": ""}

    fake_x = FakeX()
    monkeypatch.setenv("CONTENT_APPROVAL_MODE", "manual")
    get_settings.cache_clear()

    _, _, warnings, status = await publish_report(
        report_id="report-1",
        channels=["x"],
        approval_mode="auto",
        state_store=store,
        notion_adapter=FakeNotion(),
        x_adapter=fake_x,
    )

    assert status == "partial"
    assert fake_x.approval_modes == ["manual"]
    assert any("Falling back to manual approval" in warning for warning in warnings)
    get_settings.cache_clear()
