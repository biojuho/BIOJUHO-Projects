from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace


class FakeBrain:
    def analyze_news(self, category, articles):
        return {
            "summary": [f"{category} summary"],
            "insights": [{"topic": category, "insight": "detail", "importance": "high"}],
            "x_thread": [f"{category} draft"],
        }


def make_entry(title: str, link: str, description: str = "desc") -> SimpleNamespace:
    return SimpleNamespace(title=title, link=link, description=description, published_parsed=None, updated_parsed=None)


def test_process_category_survives_source_failure_and_awaits_sleep(load_script_module, monkeypatch, tmp_path):
    module, _runtime = load_script_module("run_daily_news")
    monkeypatch.setattr(module, "NOTION_REPORTS_DATABASE_ID", "news-db")

    calls = {"sleep": 0}

    async def fake_sleep(seconds: float):
        calls["sleep"] += 1

    async def fake_fetch(url: str):
        if "bad" in url:
            raise TimeoutError("timeout")
        return [
            make_entry(
                "Fresh AI startup launches cloud platform",
                "https://fresh.example.com/article",
                "new software tech startup",
            )
        ]

    async def fake_upload(**kwargs):
        return {"id": "page-1"}

    class FakeInfographicModule:
        @staticmethod
        def create_news_card(**kwargs):
            return None

    monkeypatch.setattr(module, "fetch_feed_entries", fake_fetch)
    monkeypatch.setattr(module, "upload_to_notion", fake_upload)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    monkeypatch.setitem(sys.modules, "generate_infographic", FakeInfographicModule)

    result = asyncio.run(
        module.process_category(
            category="Tech",
            sources=[{"name": "bad", "url": "bad"}, {"name": "good", "url": "good"}],
            start=module.datetime.now() - module.timedelta(hours=1),
            end=module.datetime.now() + module.timedelta(hours=1),
            max_items=5,
            notion=object(),
            brain=FakeBrain(),
            logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
            today_str="2026-02-28",
            window_name="test",
        )
    )

    assert result["status"] == "success"
    assert result["articles"] == 1
    assert calls["sleep"] == 1


def test_run_daily_news_continues_after_category_failure(load_script_module, monkeypatch):
    module, _runtime = load_script_module("run_daily_news")
    monkeypatch.setattr(module, "NOTION_API_KEY", "token")
    monkeypatch.setattr(module, "NOTION_REPORTS_DATABASE_ID", "news-db")
    monkeypatch.setattr(module, "load_news_sources", lambda: {"Tech": [], "Economy": []})
    monkeypatch.setattr(module, "AsyncClient", lambda auth: object())
    monkeypatch.setattr(
        module, "get_extraction_window", lambda force: (module.datetime.now(), module.datetime.now(), "test")
    )

    async def fake_process_category(**kwargs):
        if kwargs["category"] == "Tech":
            return {"category": "Tech", "status": "success", "articles": 2}
        return {"category": "Economy", "status": "failed", "articles": 1, "error": "boom"}

    monkeypatch.setattr(module, "process_category", fake_process_category)
    monkeypatch.setitem(sys.modules, "brain_module", SimpleNamespace(BrainModule=FakeBrain))

    exit_code = asyncio.run(module.run_daily_news(force=True, max_items=5, run_id="run-daily-news"))

    assert exit_code == 0
