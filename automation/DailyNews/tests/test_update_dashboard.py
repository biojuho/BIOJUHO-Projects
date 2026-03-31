from __future__ import annotations

import asyncio


class FakeBlocksChildren:
    def __init__(self) -> None:
        self.append_calls: list[dict] = []
        self.list_payloads: list[list[dict]] = []

    async def list(self, block_id: str, start_cursor=None):
        payload = self.list_payloads.pop(0)
        return {"results": payload, "has_more": False, "next_cursor": None}

    async def append(self, block_id: str, children):
        self.append_calls.append({"block_id": block_id, "children": children})
        return {"results": children}


class FakeBlocks:
    def __init__(self) -> None:
        self.children = FakeBlocksChildren()
        self.deleted: list[str] = []

    async def delete(self, block_id: str):
        self.deleted.append(block_id)
        return {"id": block_id}


class FakePages:
    async def retrieve(self, page_id: str):
        return {"id": page_id}

    async def create(self, **kwargs):
        return {"id": "created-page"}


class FakeNotion:
    def __init__(self) -> None:
        self.blocks = FakeBlocks()
        self.pages = FakePages()

    async def search(self, **kwargs):
        return {"results": []}


def make_heading(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "heading_2",
        "heading_2": {"rich_text": [{"plain_text": text}]},
    }


def test_clear_auto_dashboard_sections_removes_only_auto_blocks(load_script_module):
    module, _runtime = load_script_module("update_dashboard")
    notion = FakeNotion()
    notion.blocks.children.list_payloads = [
        [
            make_heading("auto-head", "[AUTO_DASHBOARD] 2026-02-28"),
            {"id": "auto-callout", "type": "callout"},
            {"id": "auto-divider", "type": "divider"},
            make_heading("manual-head", "Manual Notes"),
        ]
    ]

    asyncio.run(
        module.clear_auto_dashboard_sections(
            notion,
            "page-id",
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )
    )

    assert notion.blocks.deleted == ["auto-head", "auto-callout", "auto-divider"]


def test_update_dashboard_replaces_auto_section(load_script_module, monkeypatch):
    module, _runtime = load_script_module("update_dashboard")
    notion = FakeNotion()
    notion.blocks.children.list_payloads = [
        [
            make_heading("auto-head", "[AUTO_DASHBOARD] 2026-02-27"),
            {"id": "auto-callout", "type": "callout"},
            {"id": "auto-divider", "type": "divider"},
        ]
    ]
    monkeypatch.setattr(module, "query_todays_articles", lambda logger: asyncio.sleep(0, result=[]))

    asyncio.run(
        module.update_dashboard(
            "page-id",
            notion,
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )
    )

    assert notion.blocks.deleted == ["auto-head", "auto-callout", "auto-divider"]
    assert len(notion.blocks.children.append_calls) == 1
    heading = notion.blocks.children.append_calls[0]["children"][0]
    assert heading["heading_2"]["rich_text"][0]["text"]["content"].startswith("[AUTO_DASHBOARD]")


def test_query_todays_articles_uses_database_query_endpoint(load_script_module, monkeypatch):
    module, _runtime = load_script_module("update_dashboard")
    called_urls: list[str] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            called_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(module, "NOTION_API_KEY", "token")
    monkeypatch.setattr(module, "NOTION_TASKS_DATABASE_ID", "tasks-database-id")

    asyncio.run(
        module.query_todays_articles(
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )
    )

    assert called_urls == ["https://api.notion.com/v1/databases/tasks-database-id/query"]
