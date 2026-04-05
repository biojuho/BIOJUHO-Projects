"""publish.py DB 쓰기 실패 방어 + _publish_x_draft 크래시 격리 테스트."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from antigravity_mcp.domain.models import ChannelDraft, ContentReport
from antigravity_mcp.pipelines.publish import _publish_x_draft, _safe_db_write


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_report(report_id: str = "report-test-001") -> ContentReport:
    return ContentReport(
        report_id=report_id,
        category="Tech",
        window_name="morning",
        window_start="2026-04-05T00:00:00Z",
        window_end="2026-04-05T12:00:00Z",
        summary_lines=["요약"],
        insights=["인사이트"],
        channel_drafts=[ChannelDraft(channel="x", status="draft", content="Short tweet")],
        status="draft",
        fingerprint="abc",
        created_at="2026-04-05T00:00:00Z",
        updated_at="2026-04-05T00:00:00Z",
    )


def _auto_settings(**overrides):
    defaults = {"auto_push_enabled": True, "x_daily_post_limit": 50}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── _safe_db_write tests ────────────────────────────────────────────────────


class TestSafeDbWrite:
    def test_normal_call_succeeds(self):
        mock_fn = MagicMock()
        warnings: list[str] = []
        _safe_db_write(mock_fn, "arg1", "arg2", warnings=warnings, label="test_op")
        mock_fn.assert_called_once_with("arg1", "arg2")
        assert warnings == []

    def test_db_error_logs_warning_instead_of_crash(self):
        mock_fn = MagicMock(side_effect=OSError("database is locked"))
        warnings: list[str] = []
        _safe_db_write(mock_fn, "arg1", warnings=warnings, label="save_report")
        assert len(warnings) == 1
        assert "save_report failed" in warnings[0]
        assert "database is locked" in warnings[0]

    def test_kwargs_forwarded_correctly(self):
        mock_fn = MagicMock()
        warnings: list[str] = []
        _safe_db_write(mock_fn, "run-1", warnings=warnings, label="job_finish", status="success", summary={})
        mock_fn.assert_called_once_with("run-1", status="success", summary={})


# ── _publish_x_draft DB failure isolation ────────────────────────────────────


class TestPublishXDraftDbResilience:
    @pytest.mark.asyncio
    async def test_db_lock_during_tweet_record_does_not_crash(self):
        """record_published_tweet_id가 DB 잠금으로 실패해도 발행 흐름은 계속된다."""
        report = _make_report()
        draft = ChannelDraft(channel="x", status="draft", content="Short tweet")
        state_store = MagicMock()
        state_store.record_published_tweet_id.side_effect = OSError("database is locked")
        state_store.set_channel_publication = MagicMock()

        x_adapter = MagicMock()
        x_adapter.publish = AsyncMock(return_value={
            "status": "published",
            "tweet_url": "https://twitter.com/i/web/status/12345",
        })

        warnings: list[str] = []
        publication: dict[str, str] = {}

        with (
            patch("antigravity_mcp.pipelines.publish.XAdapter", MagicMock()),
        ):
            await _publish_x_draft(
                draft, report, "report-test-001", x_adapter, state_store,
                "auto", publication, warnings,
            )

        # 트윗은 발행됨
        assert publication["x_status"] == "published"
        # DB 오류가 warnings에 기록됨
        assert any("record_published_tweet_id failed" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_set_channel_publication_failure_recorded(self):
        """set_channel_publication DB 실패 시 warnings에 기록되고 크래시하지 않음."""
        report = _make_report()
        draft = ChannelDraft(channel="x", status="draft", content="Short tweet")
        state_store = MagicMock()
        state_store.set_channel_publication.side_effect = OSError("disk full")

        x_adapter = MagicMock()
        x_adapter.publish = AsyncMock(return_value={"status": "published", "tweet_url": ""})

        warnings: list[str] = []
        publication: dict[str, str] = {}

        await _publish_x_draft(
            draft, report, "report-test-001", x_adapter, state_store,
            "auto", publication, warnings,
        )

        assert any("set_channel_publication failed" in w for w in warnings)
