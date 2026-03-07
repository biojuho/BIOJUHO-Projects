from __future__ import annotations

from antigravity_mcp.config import get_settings


def test_settings_support_legacy_aliases(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("NOTION_API_KEY", "secret-test")
    monkeypatch.delenv("NOTION_TASKS_DATABASE_ID", raising=False)
    monkeypatch.setenv("ANTIGRAVITY_TASKS_DB_ID", "legacy-tasks-db")
    monkeypatch.setenv("ANTIGRAVITY_NEWS_DB_ID", "legacy-reports-db")
    monkeypatch.setenv("DASHBOARD_PAGE_ID", "legacy-dashboard")

    settings = get_settings()

    assert settings.notion_tasks_database_id == "legacy-tasks-db"
    assert settings.notion_reports_database_id == "legacy-reports-db"
    assert settings.notion_dashboard_page_id == "legacy-dashboard"
    assert any("deprecated" in warning.lower() for warning in settings.settings_warnings)

    get_settings.cache_clear()
