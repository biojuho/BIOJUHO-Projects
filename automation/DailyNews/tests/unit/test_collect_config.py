from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from antigravity_mcp.pipelines.collect import collect_content_items, load_sources
from antigravity_mcp.state.store import PipelineStateStore


@pytest.fixture
def state_store(tmp_path):
    store = PipelineStateStore(path=tmp_path / "collect_state.db")
    try:
        yield store
    finally:
        store.close()


def test_load_sources_returns_empty_on_invalid_json(tmp_path, monkeypatch) -> None:
    bad_file = tmp_path / "news_sources.json"
    bad_file.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.get_settings",
        lambda: SimpleNamespace(news_sources_file=bad_file),
    )

    assert load_sources() == {}


def test_load_sources_skips_malformed_entries(tmp_path, monkeypatch) -> None:
    config_file = tmp_path / "news_sources.json"
    config_file.write_text(
        json.dumps(
            {
                "Tech": [
                    {"name": "Valid", "url": "https://example.com/rss"},
                    {"name": "MissingUrl"},
                    "not-a-dict",
                ],
                "Broken": {"name": "WrongShape"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.get_settings",
        lambda: SimpleNamespace(news_sources_file=config_file),
    )

    assert load_sources() == {
        "Tech": [{"name": "Valid", "url": "https://example.com/rss"}],
    }


@pytest.mark.asyncio
async def test_collect_content_items_warns_when_source_config_unavailable(state_store, monkeypatch) -> None:
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.get_settings",
        lambda: SimpleNamespace(pipeline_max_concurrency=2),
    )
    monkeypatch.setattr("antigravity_mcp.pipelines.collect.load_sources", lambda: {})

    items, warnings = await collect_content_items(
        categories=["Tech"],
        window_name="manual",
        max_items=5,
        state_store=state_store,
        feed_adapter=MagicMock(),
    )

    assert items == []
    assert warnings == ["Source configuration unavailable or empty."]


@pytest.mark.asyncio
async def test_collect_content_items_warns_when_category_has_no_sources(state_store, monkeypatch) -> None:
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.get_settings",
        lambda: SimpleNamespace(pipeline_max_concurrency=2),
    )
    monkeypatch.setattr(
        "antigravity_mcp.pipelines.collect.load_sources",
        lambda: {"Economy": [{"name": "A", "url": "https://example.com/rss"}]},
    )

    items, warnings = await collect_content_items(
        categories=["Tech"],
        window_name="manual",
        max_items=5,
        state_store=state_store,
        feed_adapter=MagicMock(),
    )

    assert items == []
    assert warnings == ["No sources configured for category 'Tech'."]
