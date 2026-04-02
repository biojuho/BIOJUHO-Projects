from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExportPipeline:
    def test_export_daily_report_json_writes_filtered_payload(self, tmp_path: Path):
        from antigravity_mcp.pipelines.export import export_daily_report_json

        run_same_day = MagicMock(started_at="2026-04-01T01:00:00+00:00")
        run_same_day.to_dict.return_value = {"run_id": "run-1"}
        run_other_day = MagicMock(started_at="2026-03-31T23:00:00+00:00")
        run_other_day.to_dict.return_value = {"run_id": "run-2"}

        store = MagicMock()
        store.list_runs.return_value = [run_same_day, run_other_day]
        store.get_token_usage_stats.return_value = {"estimated_cost_usd": 1.23}
        store.get_metrics_summary.return_value = {"total_tweets": 2}
        store.get_top_tweets.return_value = [{"tweet_id": "123"}]
        store.get_pipeline_health.return_value = {"error_rate": 0.1}

        settings = MagicMock(output_dir=tmp_path)
        with patch("antigravity_mcp.pipelines.export.get_settings", return_value=settings):
            result = export_daily_report_json(date="2026-04-01", output_dir=tmp_path, state_store=store)

        file_path = Path(result["file_path"])
        payload = json.loads(file_path.read_text(encoding="utf-8"))

        assert result["runs_count"] == 1
        assert result["tweets_count"] == 2
        assert payload["date"] == "2026-04-01"
        assert payload["pipeline_runs"] == [{"run_id": "run-1"}]
        assert payload["tweet_metrics"]["top_tweets"] == [{"tweet_id": "123"}]

    def test_export_performance_csv_writes_rows_and_truncates_preview(self, tmp_path: Path):
        from antigravity_mcp.pipelines.export import export_performance_csv

        output_path = tmp_path / "tweet_metrics.csv"
        store = MagicMock()
        store.get_top_tweets.return_value = [
            {
                "tweet_id": "1",
                "report_id": "report-1",
                "impressions": 1000,
                "likes": 50,
                "retweets": 5,
                "replies": 2,
                "quotes": 1,
                "bookmarks": 3,
                "published_at": "2026-04-01T02:00:00+00:00",
                "content_preview": "x" * 120,
            }
        ]

        settings = MagicMock(output_dir=tmp_path)
        with patch("antigravity_mcp.pipelines.export.get_settings", return_value=settings):
            result = export_performance_csv(days=14, output_path=output_path, state_store=store)

        csv_text = output_path.read_text(encoding="utf-8")

        assert result == {"file_path": str(output_path), "rows": 1, "days": 14}
        assert "tweet_id,report_id,impressions" in csv_text
        assert ("x" * 100) in csv_text
        assert ("x" * 101) not in csv_text


class TestInsightAdapter:
    @pytest.mark.asyncio
    async def test_generate_insights_returns_generator_result_and_logs_degradation(self, monkeypatch):
        from antigravity_mcp.integrations.insight_adapter import InsightAdapter

        adapter = InsightAdapter(llm_adapter=object(), state_store=object())
        result_payload = {"insights": [], "error": "LLM adapter unavailable"}
        generate = AsyncMock(return_value=result_payload)
        monkeypatch.setattr(adapter, "_generator", MagicMock(generate_insights=generate))

        result = await adapter.generate_insights("Tech", [{"title": "A"}])

        assert adapter.is_available() is True
        assert result == result_payload
        generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_insight_report_filters_invalid_items_and_returns_x_form(self, monkeypatch):
        from antigravity_mcp.integrations.insight_adapter import InsightAdapter

        adapter = InsightAdapter(llm_adapter=object(), state_store=object())
        generate = AsyncMock(
            return_value={
                "insights": [
                    {"title": "Keep", "content": "validated", "validation_passed": True},
                    {"title": "Skip", "content": "invalid", "validation_passed": False},
                ],
                "x_long_form": "long form text",
            }
        )
        monkeypatch.setattr(adapter, "generate_insights", generate)

        summary_lines, insights, x_long_form = await adapter.generate_insight_report("Tech", [{"title": "A"}])

        assert summary_lines == ["1. Keep"]
        assert insights == ["[인사이트 1] validated"]
        assert x_long_form == "long form text"


class TestSchedulerAdapter:
    def test_get_optimal_hours_uses_default_windows_and_limits_count(self):
        from antigravity_mcp.integrations.scheduler_adapter import SchedulerAdapter

        adapter = SchedulerAdapter()
        ranked = adapter.get_optimal_hours(count=3, target_date=__import__("datetime").datetime(2026, 4, 1, 0, 0))

        assert len(ranked) == 3
        assert ranked[0]["weight"] >= ranked[-1]["weight"]

    def test_get_optimal_hours_blends_historical_performance(self):
        from antigravity_mcp.integrations.scheduler_adapter import SchedulerAdapter

        store = MagicMock()
        store.get_top_tweets.return_value = [
            {"published_at": "2026-03-01T12:00:00+00:00", "impressions": 500},
            {"published_at": "2026-03-02T12:30:00+00:00", "impressions": 1500},
            {"published_at": "bad-value", "impressions": 999},
            {"published_at": "2026-03-03T03:00:00+00:00", "impressions": 100},
            {"published_at": "2026-03-04T03:00:00+00:00", "impressions": 100},
        ]

        adapter = SchedulerAdapter(state_store=store)
        ranked = adapter.get_optimal_hours(count=6, target_date=__import__("datetime").datetime(2026, 4, 1, 0, 0))

        assert any(item["hour"] == 21 for item in ranked[:2])

    def test_get_optimal_hours_swallows_store_errors(self):
        from antigravity_mcp.integrations.scheduler_adapter import SchedulerAdapter

        store = MagicMock()
        store.get_top_tweets.side_effect = RuntimeError("db down")

        adapter = SchedulerAdapter(state_store=store)
        ranked = adapter.get_optimal_hours(count=2, target_date=__import__("datetime").datetime(2026, 4, 1, 0, 0))

        assert len(ranked) == 2

    def test_should_post_now_and_next_posting_slot(self, monkeypatch):
        import antigravity_mcp.integrations.scheduler_adapter as scheduler_module

        class FakeDateTime:
            @classmethod
            def now(cls, tz=None):
                return __import__("datetime").datetime(2026, 4, 1, 12, 10)

        monkeypatch.setattr(scheduler_module, "datetime", FakeDateTime)

        adapter = scheduler_module.SchedulerAdapter()
        monkeypatch.setattr(
            adapter,
            "get_optimal_hours",
            lambda count=3, target_date=None: [
                {"hour": 21, "weight": 1.0},
                {"hour": 22, "weight": 0.8},
                {"hour": 8, "weight": 0.7},
            ][:count],
        )

        assert adapter.should_post_now(tolerance_minutes=15) is True

        monkeypatch.setattr(
            adapter,
            "get_optimal_hours",
            lambda count=6, target_date=None: [
                {"hour": 22, "weight": 0.8},
                {"hour": 8, "weight": 0.7},
            ][:count],
        )
        assert adapter.get_next_posting_slot() == {"hour_kst": 22, "weight": 0.8}

        monkeypatch.setattr(
            adapter,
            "get_optimal_hours",
            lambda count=6, target_date=None: [
                {"hour": 8, "weight": 0.7},
                {"hour": 7, "weight": 0.6},
            ][:count],
        )
        assert adapter.get_next_posting_slot() == {"hour_kst": 8, "weight": 0.7, "tomorrow": True}
