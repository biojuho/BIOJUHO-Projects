"""storage.py 테스트: SQLite 배치 저장, Notion 재시도 로직."""

import unittest
from unittest.mock import MagicMock, patch

import aiosqlite
import pytest

from config import AppConfig
from db import init_db, save_tweets_batch
from models import (
    GeneratedThread,
    GeneratedTweet,
    MultiSourceContext,
    ScoredTrend,
    TrendSource,
    TweetBatch,
)


async def _in_memory_conn() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await init_db(conn)
    return conn


def _make_trend() -> ScoredTrend:
    return ScoredTrend(
        keyword="테스트 키워드",
        rank=1,
        viral_potential=80,
        trend_acceleration="+5%",
        top_insight="핵심",
        suggested_angles=["앵글1"],
        best_hook_starter="훅",
        context=MultiSourceContext(),
        sources=[TrendSource.GETDAYTRENDS],
    )


def _make_batch(n_tweets: int = 5, with_thread: bool = False) -> TweetBatch:
    tweets = [
        GeneratedTweet(tweet_type=f"유형{i}", content=f"트윗{i}" * 10, content_type="short") for i in range(n_tweets)
    ]
    thread = GeneratedThread(tweets=["훅 트윗 내용", "마무리 CTA"]) if with_thread else None
    return TweetBatch(topic="테스트 키워드", tweets=tweets, thread=thread)


class TestSaveTweetsBatch(unittest.IsolatedAsyncioTestCase):
    """db.save_tweets_batch 배치 저장 검증."""

    async def asyncSetUp(self):
        self.conn = await _in_memory_conn()
        # runs + trends 더미 row 생성
        await self.conn.execute(
            "INSERT INTO runs (run_uuid, started_at, country) VALUES ('uuid-1', '2024-01-01', 'korea')"
        )
        await self.conn.execute(
            """INSERT INTO trends (run_id, keyword, rank, scored_at, fingerprint)
               VALUES (1, '테스트', 1, '2024-01-01T00:00:00', 'fp1')"""
        )
        await self.conn.commit()

    async def asyncTearDown(self):
        await self.conn.close()

    @pytest.mark.asyncio
    async def test_batch_insert_count(self):
        tweets = [GeneratedTweet(tweet_type=f"유형{i}", content=f"내용{i}", content_type="short") for i in range(5)]
        await save_tweets_batch(self.conn, tweets, trend_id=1, run_id=1)
        await self.conn.commit()
        cursor = await self.conn.execute("SELECT COUNT(*) FROM tweets WHERE trend_id=1")
        row = await cursor.fetchone()
        count = row[0]
        self.assertEqual(count, 5)

    @pytest.mark.asyncio
    async def test_thread_batch_flags(self):
        thread_texts = ["훅 내용", "마무리 CTA"]
        await save_tweets_batch(self.conn, thread_texts, trend_id=1, run_id=1, is_thread=True)
        await self.conn.commit()
        cursor = await self.conn.execute(
            "SELECT is_thread, thread_order FROM tweets WHERE trend_id=1 ORDER BY thread_order"
        )
        rows = await cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["is_thread"], 1)
        self.assertEqual(rows[1]["thread_order"], 1)


class TestNotionRetryLogic(unittest.IsolatedAsyncioTestCase):
    """_retry_notion_call 지수 백오프 재시도 검증."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        from storage import _retry_notion_call

        fn = MagicMock(return_value="ok")
        result = _retry_notion_call(fn, "arg1")
        self.assertEqual(result, "ok")
        fn.assert_called_once_with("arg1")

    @pytest.mark.asyncio
    async def test_raises_non_retryable(self):
        from storage import _retry_notion_call

        fn = MagicMock(side_effect=ValueError("non-retryable"))
        with self.assertRaises(ValueError):
            _retry_notion_call(fn)

    @patch("storage.NOTION_AVAILABLE", False)
    @pytest.mark.asyncio
    async def test_notion_unavailable_returns_false(self):
        from storage import save_to_notion

        cfg = AppConfig()
        batch = _make_batch()
        trend = _make_trend()
        result = save_to_notion(batch, trend, cfg)
        self.assertFalse(result)


def test_save_to_notion_returns_false_on_provider_error():
    from storage import save_to_notion

    class FakeNotionProviderError(Exception):
        pass

    cfg = AppConfig()
    cfg.notion_token = "secret"
    cfg.notion_database_id = "db-123"
    batch = _make_batch()
    trend = _make_trend()

    with (
        patch("storage.NOTION_AVAILABLE", True),
        patch("storage.NotionClient", return_value=MagicMock()),
        patch("storage.APIResponseError", FakeNotionProviderError),
        patch("storage._notion_page_exists", side_effect=FakeNotionProviderError("rate limited")),
    ):
        assert save_to_notion(batch, trend, cfg) is False


def test_save_to_google_sheets_returns_false_on_provider_error():
    from storage import save_to_google_sheets

    class FakeSheetsProviderError(Exception):
        pass

    cfg = AppConfig()
    cfg.google_service_json = "service-account.json"
    cfg.google_sheet_id = "sheet-123"
    batch = _make_batch()
    trend = _make_trend()
    mock_credentials = MagicMock()
    mock_credentials.from_service_account_file.side_effect = FakeSheetsProviderError("bad credentials")

    with (
        patch("storage.GSPREAD_AVAILABLE", True),
        patch("storage.GoogleAuthError", FakeSheetsProviderError),
        patch("storage.Credentials", mock_credentials),
    ):
        assert save_to_google_sheets(batch, trend, cfg) is False


if __name__ == "__main__":
    unittest.main()


def test_content_hub_upsert_is_idempotent():
    from storage import save_to_content_hub

    cfg = AppConfig()
    cfg.notion_token = "secret"
    cfg.content_hub_database_id = "hub-db"
    batch = _make_batch()
    batch.metadata["workflow_v2"] = {
        "drafts": [
            {
                "draft_id": "draft-123",
                "trend_id": "trend-123",
                "platform": "x",
                "passed": True,
                "prompt_version": "getdaytrends-v2",
                "qa_score": 88.0,
                "blocking_reasons": [],
            }
        ]
    }
    trend = _make_trend()

    mock_notion = MagicMock()
    mock_notion.databases.retrieve.return_value = {
        "properties": {
            "Name": {},
            "Status": {},
            "Category": {},
            "Date": {},
            "Score": {},
            "Platform": {},
            "Trend ID": {},
            "Draft ID": {},
            "Prompt Version": {},
            "QA Score": {},
            "Blocking Reasons": {},
            "Published URL": {},
            "Published At": {},
            "Receipt ID": {},
        }
    }
    mock_notion.databases.query.return_value = {"results": [{"id": "existing-page"}]}

    with (
        patch("storage.NOTION_AVAILABLE", True),
        patch("storage.NotionClient", return_value=mock_notion),
        patch("storage._build_notion_body", return_value=[]),
        patch("storage._persist_content_hub_link") as persist_link,
    ):
        assert save_to_content_hub(batch, trend, cfg, platform="x") is True

    mock_notion.pages.update.assert_called_once()
    mock_notion.pages.create.assert_not_called()
    persist_link.assert_called_once_with(cfg, "draft-123", "existing-page", "Ready")


def test_content_hub_create_seeds_feedback_defaults():
    from storage import save_to_content_hub

    cfg = AppConfig()
    cfg.notion_token = "secret"
    cfg.content_hub_database_id = "hub-db"
    batch = _make_batch()
    batch.metadata["workflow_v2"] = {
        "drafts": [
            {
                "draft_id": "draft-456",
                "trend_id": "trend-456",
                "platform": "x",
                "passed": True,
                "prompt_version": "getdaytrends-v2",
                "qa_score": 91.0,
                "blocking_reasons": [],
            }
        ]
    }
    trend = _make_trend()

    mock_notion = MagicMock()
    mock_notion.databases.retrieve.return_value = {
        "properties": {
            "Name": {},
            "Status": {},
            "Category": {},
            "Date": {},
            "Score": {},
            "Platform": {},
            "Trend ID": {},
            "Draft ID": {},
            "Prompt Version": {},
            "QA Score": {},
            "Blocking Reasons": {},
            "Feedback State": {},
            "Next Action": {},
            "Priority": {},
        }
    }
    mock_notion.databases.query.return_value = {"results": []}
    mock_notion.pages.create.return_value = {"id": "new-page"}

    with (
        patch("storage.NOTION_AVAILABLE", True),
        patch("storage.NotionClient", return_value=mock_notion),
        patch("storage._build_notion_body", return_value=[]),
        patch("storage._persist_content_hub_link") as persist_link,
    ):
        assert save_to_content_hub(batch, trend, cfg, platform="x") is True

    mock_notion.pages.update.assert_not_called()
    mock_notion.pages.create.assert_called_once()
    created_properties = mock_notion.pages.create.call_args.kwargs["properties"]
    assert created_properties["Feedback State"]["select"]["name"] == "Need Review"
    assert created_properties["Next Action"]["select"]["name"] == "Review Copy"
    assert created_properties["Priority"]["select"]["name"] == "High"
    persist_link.assert_called_once_with(cfg, "draft-456", "new-page", "Ready")
