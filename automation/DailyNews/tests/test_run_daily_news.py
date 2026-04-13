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


def _install_run_daily_news_stubs(module, monkeypatch, *, sources):
    monkeypatch.setattr(module, "NOTION_API_KEY", "token")
    monkeypatch.setattr(module, "NOTION_REPORTS_DATABASE_ID", "news-db")
    monkeypatch.setattr(module, "load_news_sources", lambda: sources)
    monkeypatch.setattr(module, "AsyncClient", lambda auth: object())
    monkeypatch.setattr(
        module, "get_extraction_window",
        lambda force: (module.datetime.now(), module.datetime.now(), "test"),
    )

    async def _fake_resolve(notion, db_id):
        return "Name"

    monkeypatch.setattr(module, "resolve_title_property", _fake_resolve)
    monkeypatch.setitem(sys.modules, "brain_module", SimpleNamespace(BrainModule=FakeBrain))


def test_run_daily_news_partial_failure_exits_nonzero(load_script_module, monkeypatch):
    """Any category failure must surface as exit 1 — partial success still
    fires the failure alert, otherwise a single broken category could hide
    for days under the previous degraded-heartbeat path."""
    module, _runtime = load_script_module("run_daily_news")
    _install_run_daily_news_stubs(
        module, monkeypatch, sources={"Tech": [], "Economy": []}
    )

    async def fake_process_category(**kwargs):
        if kwargs["category"] == "Tech":
            return {"category": "Tech", "status": "success", "articles": 2}
        return {"category": "Economy", "status": "failed", "articles": 1, "error": "boom"}

    monkeypatch.setattr(module, "process_category", fake_process_category)

    exit_code = asyncio.run(module.run_daily_news(force=True, max_items=5, run_id="run-daily-news"))

    assert exit_code == 1


def test_run_daily_news_all_success_exits_zero(load_script_module, monkeypatch):
    module, _runtime = load_script_module("run_daily_news")
    _install_run_daily_news_stubs(
        module, monkeypatch, sources={"Tech": [], "Economy": []}
    )

    async def fake_process_category(**kwargs):
        return {"category": kwargs["category"], "status": "success", "articles": 3}

    monkeypatch.setattr(module, "process_category", fake_process_category)

    exit_code = asyncio.run(module.run_daily_news(force=True, max_items=5, run_id="run-daily-news"))

    assert exit_code == 0


def test_get_extraction_window_absorbs_cron_delay(load_script_module, monkeypatch):
    """GHA cron delays of a few hours should still classify into the right
    window. Previously 12:00 KST or 19:49 KST would raise 'outside extraction
    window' — see 2026-04-13 evening incident."""
    module, _runtime = load_script_module("run_daily_news")
    KST = module.timezone(module.timedelta(hours=9))

    real_dt = module.datetime

    class FrozenDatetime(real_dt):
        _frozen = real_dt(2026, 4, 13, 12, 30, tzinfo=KST)  # 12:30 KST, late morning cron

        @classmethod
        def now(cls, tz=None):
            return cls._frozen.astimezone(tz) if tz else cls._frozen.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    start, end, name = module.get_extraction_window(force=False)
    assert name == "morning"
    assert end.hour == 7 and start.hour == 18

    FrozenDatetime._frozen = real_dt(2026, 4, 13, 19, 49, tzinfo=KST)  # 19:49 KST, late evening cron
    start, end, name = module.get_extraction_window(force=False)
    assert name == "evening"
    assert end.hour == 18 and start.hour == 7


def test_get_extraction_window_still_rejects_dead_hours(load_script_module, monkeypatch):
    """03:00 KST is before the morning window opens; keep rejecting so
    accidental manual runs at random times still need --force."""
    module, _runtime = load_script_module("run_daily_news")
    KST = module.timezone(module.timedelta(hours=9))
    real_dt = module.datetime

    class FrozenDatetime(real_dt):
        _frozen = real_dt(2026, 4, 13, 3, 0, tzinfo=KST)

        @classmethod
        def now(cls, tz=None):
            return cls._frozen.astimezone(tz) if tz else cls._frozen.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    try:
        module.get_extraction_window(force=False)
    except RuntimeError as exc:
        assert "outside extraction window" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for dead hours")


def test_resolve_title_property_falls_back_on_error(load_script_module, monkeypatch):
    module, _runtime = load_script_module("run_daily_news")

    class BrokenDatabases:
        async def retrieve(self, database_id):
            raise RuntimeError("boom")

    class BrokenClient:
        databases = BrokenDatabases()

    name = asyncio.run(module.resolve_title_property(BrokenClient(), "db-x"))
    assert name == "Name"


def test_resolve_title_property_reads_data_source_schema(load_script_module, monkeypatch):
    """New Notion DBs expose the title column via data_sources, not the
    top-level properties map — mirror that path."""
    module, _runtime = load_script_module("run_daily_news")

    class FakeDataSources:
        async def retrieve(self, data_source_id):
            return {
                "properties": {
                    "페이지 이름": {"type": "title"},
                    "작성일": {"type": "date"},
                }
            }

    class FakeDatabases:
        async def retrieve(self, database_id):
            return {
                "properties": {},  # new API leaves this empty
                "data_sources": [{"id": "ds-1", "name": "primary"}],
            }

    class FakeClient:
        databases = FakeDatabases()
        data_sources = FakeDataSources()

    name = asyncio.run(module.resolve_title_property(FakeClient(), "db-x"))
    assert name == "페이지 이름"
