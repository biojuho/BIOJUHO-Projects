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
