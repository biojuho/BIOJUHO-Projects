from __future__ import annotations

from unittest.mock import patch

import pytest

from config import AppConfig
from db import save_run
from models import MultiSourceContext, RunResult, ScoredTrend
from tests.conftest import make_batch


def _make_trend(keyword: str) -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=82,
        trend_acceleration="+5%",
        top_insight="test insight",
        suggested_angles=["angle"],
        best_hook_starter="hook",
        context=MultiSourceContext(),
    )


@pytest.mark.asyncio
async def test_step_save_records_false_external_save_result(memory_db):
    from getdaytrends.core.pipeline_steps import _step_save

    config = AppConfig()
    config.storage_type = "notion"
    config.dry_run = False
    config.notion_database_id = "main-db"
    config.notion_token = "token"

    run = RunResult(run_id="run-1", country="korea")
    run_id = await save_run(memory_db, run)

    with patch("getdaytrends.core.steps_save.save_to_notion", return_value=False) as save_to_notion:
        success = await _step_save(
            [_make_trend("single-db-topic")],
            [make_batch("single-db-topic")],
            config,
            memory_db,
            run,
            run_id,
        )

    assert success == 1
    assert save_to_notion.call_count == 1
    assert any("external save failed (notion)" in error for error in run.errors)


@pytest.mark.asyncio
async def test_step_save_skips_content_hub_when_disabled(memory_db):
    from getdaytrends.core.pipeline_steps import _step_save

    config = AppConfig()
    config.storage_type = "notion"
    config.dry_run = False
    config.notion_database_id = "main-db"
    config.content_hub_database_id = "hub-db"
    config.enable_content_hub = False
    config.notion_token = "token"
    config.target_platforms = ["x", "threads"]

    run = RunResult(run_id="run-2", country="korea")
    run_id = await save_run(memory_db, run)

    with patch("getdaytrends.core.steps_save.save_to_notion", return_value=True) as save_to_notion:
        with patch("getdaytrends.core.steps_save.save_to_content_hub", return_value=True) as save_to_content_hub:
            success = await _step_save(
                [_make_trend("single-db-topic")],
                [make_batch("single-db-topic")],
                config,
                memory_db,
                run,
                run_id,
            )

    assert success == 1
    assert save_to_notion.call_count == 1
    save_to_content_hub.assert_not_called()


def test_content_hub_flag_defaults_to_disabled(monkeypatch):
    monkeypatch.setenv("CONTENT_HUB_DATABASE_ID", "hub-db")
    monkeypatch.delenv("ENABLE_CONTENT_HUB", raising=False)

    config = AppConfig.from_env()

    assert config.enable_content_hub is False


def test_content_hub_flag_can_disable_existing_hub(monkeypatch):
    monkeypatch.setenv("CONTENT_HUB_DATABASE_ID", "hub-db")
    monkeypatch.setenv("ENABLE_CONTENT_HUB", "false")

    config = AppConfig.from_env()

    assert config.enable_content_hub is False


def test_content_hub_flag_can_explicitly_enable_existing_hub(monkeypatch):
    monkeypatch.setenv("CONTENT_HUB_DATABASE_ID", "hub-db")
    monkeypatch.setenv("ENABLE_CONTENT_HUB", "true")

    config = AppConfig.from_env()

    assert config.enable_content_hub is True
