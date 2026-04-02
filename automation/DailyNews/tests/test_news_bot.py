from __future__ import annotations

import asyncio
from types import SimpleNamespace


class FakePages:
    async def create(self, **kwargs):
        return {"id": "page-created", "url": "https://notion.so/page-created"}


class FakeAsyncClient:
    def __init__(self, auth: str):
        self.auth = auth
        self.pages = FakePages()


def make_entry(title: str, link: str, summary: str = "summary") -> SimpleNamespace:
    return SimpleNamespace(title=title, link=link, summary=summary, published_parsed=None)


def test_news_bot_continues_when_one_category_upload_fails(load_script_module, monkeypatch, tmp_path):
    module, runtime = load_script_module("news_bot")
    state = runtime.PipelineStateStore(tmp_path / "data" / "pipeline_state.db")
    try:
        monkeypatch.setattr(module, "PipelineStateStore", lambda: state)
        monkeypatch.setattr(module, "NOTION_API_KEY", "token")
        monkeypatch.setattr(module, "NOTION_TASKS_DATABASE_ID", "tasks-db")
        monkeypatch.setattr(module, "PIPELINE_MAX_CONCURRENCY", 2)
        monkeypatch.setattr(module, "AsyncClient", FakeAsyncClient)
        monkeypatch.setattr(
            module,
            "load_sources",
            lambda: {"Tech": [{"name": "A", "url": "tech"}], "Economy": [{"name": "B", "url": "eco"}]},
        )
        monkeypatch.setattr(module, "load_summarizer", lambda: None)
        monkeypatch.setattr(module, "load_brain", lambda logger: None)
        monkeypatch.setattr(module, "load_x_radar", lambda logger: None)
        monkeypatch.setattr(module, "load_market_data", lambda logger: None)

        async def fake_fetch(url: str):
            return [make_entry(f"title-{url}", f"https://{url}.example.com/article")]

        async def fake_create(**kwargs):
            step = kwargs["step"]
            if step == "upload:Economy":
                raise RuntimeError("upload failed")
            return {"id": "page-tech"}

        monkeypatch.setattr(module, "fetch_feed_entries", fake_fetch)
        monkeypatch.setattr(module, "create_notion_page_with_retry", fake_create)

        exit_code = asyncio.run(module.run_news_bot(max_items=5, run_id="run-news-1"))

        assert exit_code == 0
        assert state.has_article("https://tech.example.com/article")
        assert not state.has_article("https://eco.example.com/article")
    finally:
        state.close()


def test_news_bot_skips_links_already_seen(load_script_module, monkeypatch, tmp_path):
    module, runtime = load_script_module("news_bot")
    state = runtime.PipelineStateStore(tmp_path / "data" / "pipeline_state.db")
    try:
        state.record_article(link="https://dup.example.com/article", source="A", notion_page_id="page-old", run_id="seed")

        monkeypatch.setattr(module, "PipelineStateStore", lambda: state)
        monkeypatch.setattr(module, "NOTION_API_KEY", "token")
        monkeypatch.setattr(module, "NOTION_TASKS_DATABASE_ID", "tasks-db")
        monkeypatch.setattr(module, "PIPELINE_MAX_CONCURRENCY", 1)
        monkeypatch.setattr(module, "AsyncClient", FakeAsyncClient)
        monkeypatch.setattr(module, "load_sources", lambda: {"Tech": [{"name": "A", "url": "tech"}]})
        monkeypatch.setattr(module, "load_summarizer", lambda: None)
        monkeypatch.setattr(module, "load_brain", lambda logger: None)
        monkeypatch.setattr(module, "load_x_radar", lambda logger: None)
        monkeypatch.setattr(module, "load_market_data", lambda logger: None)
        monkeypatch.setattr(
            module,
            "fetch_feed_entries",
            lambda url: asyncio.sleep(0, result=[make_entry("Dup", "https://dup.example.com/article")]),
        )

        captured = {"called": False}

        async def fake_create(**kwargs):
            captured["called"] = True
            return {"id": "page-never"}

        monkeypatch.setattr(module, "create_notion_page_with_retry", fake_create)

        exit_code = asyncio.run(module.run_news_bot(max_items=5, run_id="run-news-2"))

        assert exit_code == 0
        assert captured["called"] is False
    finally:
        state.close()
