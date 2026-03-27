from __future__ import annotations

import asyncio
from types import SimpleNamespace


class FakePages:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return {"id": f"page-{len(self.created)}"}


class FakeAsyncClient:
    def __init__(self, auth: str):
        self.auth = auth
        self.pages = FakePages()


def make_entry(title: str, link: str, description: str = "desc") -> SimpleNamespace:
    return SimpleNamespace(title=title, link=link, description=description)


def test_collect_news_skips_duplicates_and_saves_new_articles(load_script_module, monkeypatch, tmp_path):
    module, runtime = load_script_module("collect_news")
    state = runtime.PipelineStateStore(tmp_path / "data" / "pipeline_state.db")
    state.record_article(link="https://cached.example.com", source="Cache", notion_page_id="old-page", run_id="seed")

    monkeypatch.setattr(module, "PipelineStateStore", lambda: state)
    monkeypatch.setattr(module, "NOTION_API_KEY", "token")
    monkeypatch.setattr(module, "ANTIGRAVITY_NEWS_DB_ID", "news-db")
    monkeypatch.setattr(module, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(module, "_load_all_feeds", lambda: {"Tech": [{"name": "FeedA", "url": "https://feed.example.com"}]})
    monkeypatch.setattr(module, "_is_relevant_to_category", lambda title, desc, cat: True)
    monkeypatch.setattr(module, "get_existing_urls", lambda database_id, api_key, logger: asyncio.sleep(0, result={"https://existing.example.com"}))
    monkeypatch.setattr(
        module,
        "fetch_feed_entries",
        lambda url: asyncio.sleep(
            0,
            result=[
                make_entry("Existing", "https://existing.example.com"),
                make_entry("Cached", "https://cached.example.com"),
                make_entry("Fresh AI startup raises funding", "https://fresh.example.com"),
            ],
        ),
    )

    exit_code = asyncio.run(module.collect_and_upload_news(max_items=10, run_id="run-collect-1"))

    assert exit_code == 0
    assert state.has_article("https://fresh.example.com")
    assert not state.has_article("https://existing.example.com")


def test_collect_news_continues_after_source_failure(load_script_module, monkeypatch, tmp_path):
    module, runtime = load_script_module("collect_news")
    state = runtime.PipelineStateStore(tmp_path / "data" / "pipeline_state.db")
    monkeypatch.setattr(module, "PipelineStateStore", lambda: state)
    monkeypatch.setattr(module, "NOTION_API_KEY", "token")
    monkeypatch.setattr(module, "ANTIGRAVITY_NEWS_DB_ID", "news-db")
    monkeypatch.setattr(module, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(module, "get_existing_urls", lambda database_id, api_key, logger: asyncio.sleep(0, result=set()))
    monkeypatch.setattr(module, "_load_all_feeds", lambda: {
        "Tech": [
            {"name": "Broken", "url": "https://broken.example.com"},
            {"name": "Healthy", "url": "https://healthy.example.com"},
        ]
    })
    monkeypatch.setattr(module, "_is_relevant_to_category", lambda title, desc, cat: True)

    async def fake_fetch(url: str):
        if "broken" in url:
            raise TimeoutError("timeout")
        return [make_entry("Healthy AI Article", "https://healthy.example.com/article")]

    monkeypatch.setattr(module, "fetch_feed_entries", fake_fetch)

    exit_code = asyncio.run(module.collect_and_upload_news(max_items=10, run_id="run-collect-2"))

    assert exit_code == 0
    assert state.has_article("https://healthy.example.com/article")


def test_get_existing_urls_uses_database_query_endpoint(load_script_module, monkeypatch):
    module, _runtime = load_script_module("collect_news")
    called_urls: list[str] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [], "has_more": False, "next_cursor": None}

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
    monkeypatch.setattr(module, "NOTION_REPORTS_DATA_SOURCE_ID", "legacy-data-source-id")

    asyncio.run(
        module.get_existing_urls(
            "reports-database-id",
            "token",
            logger=type("Logger", (), {"info": lambda *args, **kwargs: None})(),
        )
    )

    assert called_urls == ["https://api.notion.com/v1/databases/reports-database-id/query"]
