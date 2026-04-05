"""X adapter post_thread 부분 실패 방어 + 일일 제한 사전 체크 테스트."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from antigravity_mcp.integrations.x_adapter import XAdapter
from antigravity_mcp.state.store import PipelineStateStore


def _auto_settings(**overrides):
    defaults = {
        "auto_push_enabled": True,
        "x_daily_post_limit": 50,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def store(tmp_path):
    s = PipelineStateStore(path=tmp_path / "test_thread.db")
    yield s
    s.close()


class TestPostThreadResilience:
    """post_thread: 중간 트윗 실패 시 나머지 skipped 표시 + 일일 제한 사전 체크."""

    @pytest.mark.asyncio
    async def test_mid_thread_failure_marks_remaining_skipped(self, store):
        """3개 트윗 중 2번째 실패 → 3번째는 skipped으로 기록."""
        mock_client = MagicMock()
        ok_response = SimpleNamespace(data={"id": "111"})
        mock_client.create_tweet.side_effect = [ok_response, RuntimeError("rate limit"), None]

        with (
            patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True),
            patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True),
            patch.object(XAdapter, "_build_client", return_value=mock_client),
        ):
            adapter = XAdapter(state_store=store)
            adapter.settings = _auto_settings()
            results = await adapter.post_thread(["tweet1", "tweet2", "tweet3"])

        assert len(results) == 3
        assert results[0]["status"] == "published"
        assert results[1]["status"] == "error"
        assert results[2]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_thread_blocked_when_exceeds_daily_limit(self, store):
        """스레드 게시 전 일일 제한 초과 예상 시 전체 차단."""
        # 이미 9개 게시된 상태에서 3개짜리 스레드 시도 (제한 10)
        for _ in range(9):
            store.increment_x_post_count("2026-04-05")

        mock_client = MagicMock()
        with (
            patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True),
            patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True),
            patch.object(XAdapter, "_build_client", return_value=mock_client),
            patch("antigravity_mcp.integrations.x_adapter.date") as mock_date,
        ):
            mock_date.today.return_value = SimpleNamespace(isoformat=lambda: "2026-04-05")
            adapter = XAdapter(state_store=store)
            adapter.settings = _auto_settings(x_daily_post_limit=10)
            results = await adapter.post_thread(["a", "b", "c"])

        assert all(r["status"] == "blocked" for r in results)
        mock_client.create_tweet.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_thread_success(self, store):
        """정상 경로: 모든 트윗 성공."""
        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = [
            SimpleNamespace(data={"id": "1"}),
            SimpleNamespace(data={"id": "2"}),
        ]

        with (
            patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True),
            patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True),
            patch.object(XAdapter, "_build_client", return_value=mock_client),
        ):
            adapter = XAdapter(state_store=store)
            adapter.settings = _auto_settings()
            results = await adapter.post_thread(["tweet1", "tweet2"])

        assert len(results) == 2
        assert all(r["status"] == "published" for r in results)
        # reply chain 검증: 2번째 트윗은 1번째에 대한 reply
        second_call_kwargs = mock_client.create_tweet.call_args_list[1][1]
        assert second_call_kwargs["reply"] == {"in_reply_to_tweet_id": "1"}

    @pytest.mark.asyncio
    async def test_first_tweet_failure_all_remaining_skipped(self, store):
        """첫 트윗 실패 → 나머지 전부 skipped."""
        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = ConnectionError("network down")

        with (
            patch("antigravity_mcp.integrations.x_adapter._TWEEPY_AVAILABLE", True),
            patch("antigravity_mcp.integrations.x_adapter.has_credentials", return_value=True),
            patch.object(XAdapter, "_build_client", return_value=mock_client),
        ):
            adapter = XAdapter(state_store=store)
            adapter.settings = _auto_settings()
            results = await adapter.post_thread(["a", "b", "c"])

        assert results[0]["status"] == "error"
        assert results[1]["status"] == "skipped"
        assert results[2]["status"] == "skipped"
