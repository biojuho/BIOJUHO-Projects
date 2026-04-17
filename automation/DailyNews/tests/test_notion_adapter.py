from __future__ import annotations

from types import SimpleNamespace

import pytest
from antigravity_mcp.integrations.notion_adapter import NotionAdapter


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeBlocksChildren:
    def __init__(self) -> None:
        self.append_calls: list[dict] = []
        self.list_payload = {"results": [], "has_more": False, "next_cursor": None}

    async def list(self, block_id: str, start_cursor=None):
        return self.list_payload

    async def append(self, block_id: str, children):
        self.append_calls.append({"block_id": block_id, "children": children})
        return {"results": children}


class _FakeBlocks:
    def __init__(self) -> None:
        self.children = _FakeBlocksChildren()
        self.deleted: list[str] = []

    async def delete(self, block_id: str):
        self.deleted.append(block_id)
        return {"id": block_id}


class _FakePages:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []

    async def update(self, **kwargs):
        self.update_calls.append(kwargs)
        return {"id": kwargs["page_id"], "url": "https://notion.so/page"}


class _FakeClient:
    def __init__(self) -> None:
        self.blocks = _FakeBlocks()
        self.pages = _FakePages()


@pytest.mark.asyncio
async def test_query_data_source_routes_through_database_endpoint(monkeypatch):
    called_urls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            called_urls.append(url)
            return _FakeResponse({"results": [{"id": "page-1"}], "next_cursor": None})

    monkeypatch.setattr("antigravity_mcp.integrations.notion_adapter.httpx.AsyncClient", FakeAsyncClient)

    settings = SimpleNamespace(
        notion_api_version="2025-09-03",
        pipeline_http_timeout_sec=15,
        notion_api_key="token",
    )
    adapter = NotionAdapter(settings=settings, api_key="token", client=object())

    results, cursor = await adapter.query_data_source(
        data_source_id="reports-database-id",
        filter_payload={"property": "Date", "date": {"equals": "2026-03-27"}},
        limit=50,
    )

    assert len(results) == 1
    assert cursor == ""
    assert called_urls == ["https://api.notion.com/v1/databases/reports-database-id/query"]


@pytest.mark.asyncio
async def test_replace_page_markdown_deletes_existing_blocks_then_appends():
    settings = SimpleNamespace(
        notion_api_version="2022-06-28",
        pipeline_http_timeout_sec=15,
        notion_api_key="token",
    )
    client = _FakeClient()
    client.blocks.children.list_payload = {
        "results": [
            {"id": "block-1", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "old 1"}]}},
            {"id": "block-2", "type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "old 2"}]}},
        ],
        "has_more": False,
        "next_cursor": None,
    }
    adapter = NotionAdapter(settings=settings, api_key="token", client=client)

    appended = await adapter.replace_page_markdown(page_id="page-1", markdown="# Fresh Title\n\nnew body")

    assert client.blocks.deleted == ["block-1", "block-2"]
    assert appended > 0
    assert len(client.blocks.children.append_calls) == 1
    assert client.blocks.children.append_calls[0]["block_id"] == "page-1"


@pytest.mark.asyncio
async def test_update_page_passes_properties_to_client():
    settings = SimpleNamespace(
        notion_api_version="2022-06-28",
        pipeline_http_timeout_sec=15,
        notion_api_key="token",
    )
    client = _FakeClient()
    adapter = NotionAdapter(settings=settings, api_key="token", client=client)

    result = await adapter.update_page(
        page_id="page-123",
        properties={"Type": {"select": {"name": "News"}}},
    )

    assert result["id"] == "page-123"
    assert client.pages.update_calls == [
        {"page_id": "page-123", "properties": {"Type": {"select": {"name": "News"}}}}
    ]
