"""Tests for adoption plan: exception hierarchy, container polling, adapters, orchestrator."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---- Exception Hierarchy Tests ----


class TestExceptionHierarchy:
    def test_base_error(self):
        from services.meta_api import MetaAPIError

        e = MetaAPIError("test", code=42, subcode=1, fbtrace_id="abc123")
        assert e.code == 42
        assert e.subcode == 1
        assert e.fbtrace_id == "abc123"
        assert str(e) == "test"

    def test_auth_error_inherits(self):
        from services.meta_api import MetaAPIError, MetaAuthError

        e = MetaAuthError("Token expired", code=190)
        assert isinstance(e, MetaAPIError)
        assert e.code == 190

    def test_rate_limit_error(self):
        from services.meta_api import MetaAPIError, MetaRateLimitError

        e = MetaRateLimitError("Too many calls", code=4)
        assert isinstance(e, MetaAPIError)
        assert e.code == 4

    def test_permission_error(self):
        from services.meta_api import MetaAPIError, MetaPermissionError

        e = MetaPermissionError("No permission", code=10)
        assert isinstance(e, MetaAPIError)

    def test_not_found_error(self):
        from services.meta_api import MetaAPIError, MetaNotFoundError

        e = MetaNotFoundError("Resource gone", code=803)
        assert isinstance(e, MetaAPIError)

    def test_server_error(self):
        from services.meta_api import MetaAPIError, MetaServerError

        e = MetaServerError("Internal error")
        assert isinstance(e, MetaAPIError)

    def test_container_error(self):
        from services.meta_api import MetaAPIError, MetaContainerError

        e = MetaContainerError("Processing failed")
        assert isinstance(e, MetaAPIError)

    def test_catch_all_with_base(self):
        """All subclasses should be catchable with MetaAPIError."""
        from services.meta_api import (
            MetaAPIError,
            MetaAuthError,
            MetaContainerError,
            MetaNotFoundError,
            MetaPermissionError,
            MetaRateLimitError,
            MetaServerError,
        )

        for cls in [
            MetaAuthError,
            MetaRateLimitError,
            MetaPermissionError,
            MetaNotFoundError,
            MetaServerError,
            MetaContainerError,
        ]:
            try:
                raise cls("test")
            except MetaAPIError:
                pass  # Should be caught


# ---- Container Status Tests ----


class TestContainerStatus:
    def test_status_values(self):
        from services.meta_api import ContainerStatus

        assert ContainerStatus.FINISHED == "FINISHED"
        assert ContainerStatus.ERROR == "ERROR"
        assert ContainerStatus.EXPIRED == "EXPIRED"
        assert ContainerStatus.IN_PROGRESS == "IN_PROGRESS"


# ---- Platform Adapter Tests ----


class TestPlatformAdapter:
    def test_post_content_full_caption(self):
        from platform_adapters import PostContent

        content = PostContent(
            caption="Hello world",
            hashtags=["#ai", "#tech"],
        )
        assert "#ai" in content.full_caption
        assert "#tech" in content.full_caption
        assert "Hello world" in content.full_caption

    def test_post_content_no_hashtags(self):
        from platform_adapters import PostContent

        content = PostContent(caption="No tags here")
        assert content.full_caption == "No tags here"

    def test_publish_result(self):
        from platform_adapters import PublishResult

        result = PublishResult(platform="instagram", post_id="123", url="https://ig.com/p/123")
        assert result.success is True
        assert result.platform == "instagram"

    def test_publish_result_failure(self):
        from platform_adapters import PublishResult

        result = PublishResult(platform="instagram", post_id="", success=False, error="Token expired")
        assert result.success is False
        assert "Token" in result.error

    def test_instagram_adapter_exists(self):
        from platform_adapters.instagram import InstagramAdapter

        assert InstagramAdapter.platform_name == "instagram"

    def test_adapter_is_subclass(self):
        from platform_adapters import PlatformAdapter
        from platform_adapters.instagram import InstagramAdapter

        assert issubclass(InstagramAdapter, PlatformAdapter)


# ---- Orchestrator Tests ----


def _tmp_db():
    return tempfile.mktemp(suffix=".db")


class TestOrchestrator:
    def _make_orchestrator(self):
        from services.ab_testing import ABTestEngine
        from services.content_calendar import ContentCalendar
        from services.hashtag_strategy import HashtagDB
        from services.orchestrator import Orchestrator

        db = _tmp_db()
        calendar = ContentCalendar(db)
        hashtag_db = HashtagDB(db)
        hashtag_db.seed_defaults()
        ab_engine = ABTestEngine(db)

        mock_scheduler = MagicMock()
        mock_scheduler.generate_daily_content = AsyncMock()
        mock_scheduler.db = MagicMock()
        mock_scheduler.db.get_scheduled_posts = MagicMock(return_value=[])

        mock_analytics = MagicMock()

        return Orchestrator(
            calendar=calendar,
            hashtag_db=hashtag_db,
            ab_engine=ab_engine,
            scheduler=mock_scheduler,
            analytics=mock_analytics,
        )

    def test_pipeline_status(self):
        orch = self._make_orchestrator()
        status = orch.get_pipeline_status()
        assert status["status"] == "operational"
        assert "calendar" in status
        assert "hashtags" in status
        assert "ab_testing" in status

    def test_pipeline_status_with_data(self):
        orch = self._make_orchestrator()
        orch.calendar.generate_weekly_plan(posting_hours=[12])
        status = orch.get_pipeline_status()
        assert status["calendar"]["total_planned"] == 7

    @pytest.mark.asyncio
    async def test_run_daily_cycle(self):
        orch = self._make_orchestrator()
        result = await orch.run_daily_cycle()
        assert "timestamp" in result
        assert "posts_generated" in result
        assert "calendar_entries" in result

    def test_apply_learnings_empty(self):
        orch = self._make_orchestrator()
        applied = orch._apply_learnings()
        assert applied == 0

    def test_apply_learnings_with_caption(self):
        orch = self._make_orchestrator()
        # Create a completed caption test
        exp_id = orch.ab_engine.create_caption_test("test", "A", "B")
        orch.ab_engine.record_results(1, reach=100, engagement=10)
        orch.ab_engine.record_results(2, reach=100, engagement=50)
        orch.ab_engine.complete_experiment(exp_id)

        applied = orch._apply_learnings()
        assert applied >= 1
