from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config import AppConfig
from getdaytrends.core.pipeline import _step_genealogy, _step_post_run


@pytest.mark.asyncio
async def test_step_genealogy_awaits_history_and_persistence(monkeypatch):
    config = AppConfig()
    config.db_path = ":memory:"
    config.genealogy_history_hours = 48
    config.genealogy_min_confidence = 0.5

    quality_trends = [
        SimpleNamespace(keyword="alpha", viral_potential=88),
        SimpleNamespace(keyword="beta", viral_potential=61),
    ]
    expected_history = [{"keyword": "alpha", "peak_viral_score": 72}]

    tracker = SimpleNamespace(
        get_trend_history=AsyncMock(return_value=expected_history),
        save_trend_genealogy=AsyncMock(),
    )

    async def fake_analyze(current_trends, history_trends, client, cfg):
        assert current_trends == quality_trends
        assert history_trends == expected_history
        assert not asyncio.iscoroutine(history_trends)
        assert cfg is config
        return [
            {
                "keyword": "alpha",
                "parent_keyword": "parent-alpha",
                "predicted_children": ["child-alpha"],
                "confidence": 0.9,
            },
            {
                "keyword": "beta",
                "parent_keyword": "",
                "predicted_children": [],
                "confidence": 0.2,
            },
        ]

    def fake_enrich(trends, genealogy):
        assert trends == quality_trends
        assert len(genealogy) == 2
        return trends

    monkeypatch.setattr("getdaytrends.performance_tracker.PerformanceTracker", lambda db_path: tracker)
    monkeypatch.setattr("getdaytrends.analyzer.analyze_trend_genealogy", fake_analyze)
    monkeypatch.setattr("getdaytrends.analyzer.enrich_trends_with_genealogy", fake_enrich)
    monkeypatch.setattr("getdaytrends.core.pipeline.get_client", lambda: object())

    result = await _step_genealogy(quality_trends, config)

    assert result == quality_trends
    tracker.get_trend_history.assert_awaited_once_with(keyword="", hours=48)
    tracker.save_trend_genealogy.assert_awaited_once_with(
        keyword="alpha",
        parent_keyword="parent-alpha",
        predicted_children=["child-alpha"],
        viral_score=88,
    )


@pytest.mark.asyncio
async def test_step_post_run_awaits_golden_reference_update(monkeypatch):
    pipeline_config = AppConfig()
    pipeline_config.db_path = ":memory:"
    pipeline_config.enable_tiered_collection = False
    pipeline_config.enable_golden_reference_qa = True
    pipeline_config.golden_reference_auto_update_days = 9

    tracker = SimpleNamespace(auto_update_golden_references=AsyncMock(return_value=4))
    adjust_schedule = AsyncMock()

    monkeypatch.setattr("getdaytrends.performance_tracker.PerformanceTracker", lambda **kwargs: tracker)
    monkeypatch.setattr("getdaytrends.core.pipeline._adjust_schedule", adjust_schedule)

    run = SimpleNamespace(
        run_id="run-12345678",
        country="korea",
        trends_collected=0,
        trends_scored=0,
        tweets_generated=0,
        tweets_saved=0,
        errors=[],
    )

    await _step_post_run(pipeline_config, run, 1.0, [], pipeline_config, lambda: None, "===")

    tracker.auto_update_golden_references.assert_awaited_once_with(days=9)
    adjust_schedule.assert_awaited_once()


@pytest.mark.asyncio
async def test_step_post_run_swallows_best_effort_tracker_failures(monkeypatch):
    pipeline_config = AppConfig()
    pipeline_config.db_path = ":memory:"
    pipeline_config.enable_tiered_collection = True
    pipeline_config.enable_golden_reference_qa = False

    tracker = SimpleNamespace(run_tiered_collection=AsyncMock(side_effect=Exception("missing analytics table")))
    adjust_schedule = AsyncMock()

    monkeypatch.setattr("getdaytrends.performance_tracker.PerformanceTracker", lambda **kwargs: tracker)
    monkeypatch.setattr("getdaytrends.core.pipeline._adjust_schedule", adjust_schedule)

    run = SimpleNamespace(
        run_id="run-87654321",
        country="korea",
        trends_collected=0,
        trends_scored=0,
        tweets_generated=0,
        tweets_saved=0,
        errors=[],
    )

    await _step_post_run(pipeline_config, run, 1.0, [], pipeline_config, lambda: None, "===")

    tracker.run_tiered_collection.assert_awaited_once()
    adjust_schedule.assert_awaited_once()


@pytest.mark.asyncio
async def test_step_genealogy_swallows_best_effort_tracker_failures(monkeypatch):
    config = AppConfig()
    config.db_path = ":memory:"

    quality_trends = [SimpleNamespace(keyword="alpha", viral_potential=88)]
    tracker = SimpleNamespace(
        get_trend_history=AsyncMock(side_effect=Exception("trend_genealogy table missing")),
        save_trend_genealogy=AsyncMock(),
    )

    monkeypatch.setattr("getdaytrends.performance_tracker.PerformanceTracker", lambda db_path: tracker)

    result = await _step_genealogy(quality_trends, config)

    assert result == quality_trends
    tracker.get_trend_history.assert_awaited_once()
    tracker.save_trend_genealogy.assert_not_called()
