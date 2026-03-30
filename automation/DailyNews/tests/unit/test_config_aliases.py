from __future__ import annotations

import json

from antigravity_mcp.config import get_settings


def test_settings_support_legacy_aliases(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("NOTION_API_KEY", "secret-test")
    monkeypatch.delenv("NOTION_TASKS_DATABASE_ID", raising=False)
    monkeypatch.delenv("NOTION_REPORTS_DATABASE_ID", raising=False)
    monkeypatch.delenv("NOTION_DASHBOARD_PAGE_ID", raising=False)
    monkeypatch.setenv("ANTIGRAVITY_TASKS_DB_ID", "legacy-tasks-db")
    monkeypatch.setenv("ANTIGRAVITY_NEWS_DB_ID", "legacy-reports-db")
    monkeypatch.setenv("DASHBOARD_PAGE_ID", "legacy-dashboard")

    settings = get_settings()

    assert settings.notion_tasks_database_id == "legacy-tasks-db"
    assert settings.notion_reports_database_id == "legacy-reports-db"
    assert settings.notion_dashboard_page_id == "legacy-dashboard"
    assert any("deprecated" in warning.lower() for warning in settings.settings_warnings)

    get_settings.cache_clear()


def test_settings_fall_back_to_dashboard_config(monkeypatch, tmp_path):
    from antigravity_mcp import config as config_module

    get_settings.cache_clear()
    monkeypatch.setenv("NOTION_API_KEY", "secret-test")
    monkeypatch.delenv("NOTION_DASHBOARD_PAGE_ID", raising=False)
    monkeypatch.delenv("DASHBOARD_PAGE_ID", raising=False)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "dashboard_config.json").write_text(
        json.dumps({"dashboard_page_id": "config-dashboard-id"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)

    settings = get_settings()

    assert settings.notion_dashboard_page_id == "config-dashboard-id"
    assert any("dashboard_config.json fallback" in warning for warning in settings.settings_warnings)

    get_settings.cache_clear()
