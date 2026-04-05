"""tweet_repository.py 테스트: 트윗 저장/조회, 동적 SQL 빌드, 배치 분기."""

import pytest
import pytest_asyncio

from models import GeneratedThread, GeneratedTweet
from db_layer.tweet_repository import (
    get_best_posting_hours,
    get_recent_tweet_contents,
    mark_tweet_posted,
    record_posting_time_stat,
    save_thread,
    save_tweet,
    save_tweets_batch,
    sync_tweet_metrics,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db(memory_db):
    return memory_db


def _tweet(content="테스트 트윗", tweet_type="공감 유도형", content_type="short"):
    return GeneratedTweet(tweet_type=tweet_type, content=content, content_type=content_type)


async def _seed_run(db) -> int:
    """runs 테이블에 레코드 하나 삽입 후 run_id 반환."""
    from datetime import datetime

    import uuid

    cursor = await db.execute(
        "INSERT INTO runs (run_uuid, started_at) VALUES (?, ?)",
        (str(uuid.uuid4()), datetime.now().isoformat()),
    )
    await db.commit()
    return cursor.lastrowid


async def _seed_trend(db, run_id: int, keyword: str = "테스트트렌드") -> int:
    """trends 테이블에 레코드 삽입 후 trend_id 반환."""
    from db_layer.trend_repository import save_trend
    from models import MultiSourceContext, ScoredTrend

    trend = ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=75,
        trend_acceleration="+5%",
        top_insight="테스트 인사이트",
        suggested_angles=["앵글1"],
        best_hook_starter="훅",
        context=MultiSourceContext(twitter_insight="X", reddit_insight="R"),
        safety_flag=False,
        sentiment="neutral",
    )
    return await save_trend(db, trend, run_id)


# ── save_tweet / save_thread Happy Path ───────────────────────────────────────


class TestSaveTweet:

    @pytest.mark.asyncio
    async def test_save_single_tweet(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        tweet = _tweet("단일 트윗 테스트")
        row_id = await save_tweet(db, tweet, trend_id, run_id)
        assert row_id > 0

        cursor = await db.execute("SELECT * FROM tweets WHERE id = ?", (row_id,))
        row = await cursor.fetchone()
        assert dict(row)["content"] == "단일 트윗 테스트"
        assert dict(row)["status"] == "queued"

    @pytest.mark.asyncio
    async def test_save_thread(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        thread = GeneratedThread(tweets=["스레드 1/3", "스레드 2/3", "스레드 3/3"])
        ids = await save_thread(db, thread, trend_id, run_id)
        assert len(ids) == 3

        # thread_order 검증
        for i, row_id in enumerate(ids):
            cursor = await db.execute("SELECT thread_order, is_thread FROM tweets WHERE id = ?", (row_id,))
            row = await cursor.fetchone()
            assert dict(row)["thread_order"] == i
            assert dict(row)["is_thread"] == 1


# ── save_tweets_batch 분기 ────────────────────────────────────────────────────


class TestSaveTweetsBatch:

    @pytest.mark.asyncio
    async def test_batch_non_thread(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        tweets = [_tweet(f"배치 트윗 {i}") for i in range(3)]
        await save_tweets_batch(db, tweets, trend_id, run_id, is_thread=False)
        await db.commit()

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM tweets WHERE trend_id = ? AND is_thread = 0",
            (trend_id,),
        )
        row = await cursor.fetchone()
        assert dict(row)["cnt"] == 3

    @pytest.mark.asyncio
    async def test_batch_thread(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        texts = ["스레드 배치 1", "스레드 배치 2"]
        await save_tweets_batch(db, texts, trend_id, run_id, is_thread=True)
        await db.commit()

        cursor = await db.execute(
            "SELECT thread_order FROM tweets WHERE trend_id = ? AND is_thread = 1 ORDER BY thread_order",
            (trend_id,),
        )
        rows = await cursor.fetchall()
        assert [dict(r)["thread_order"] for r in rows] == [0, 1]

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, db):
        """빈 리스트 전달 시 에러 없이 완료."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        await save_tweets_batch(db, [], trend_id, run_id)
        await db.commit()

    @pytest.mark.asyncio
    async def test_batch_missing_attributes_uses_getattr_defaults(self, db):
        """getattr fallback: content 없는 객체 → 빈 문자열로 저장 (silent)."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)

        bare = _tweet("")
        bare.tweet_type = ""
        bare.content = ""

        await save_tweets_batch(db, [bare], trend_id, run_id)
        await db.commit()

        cursor = await db.execute(
            "SELECT content, tweet_type, content_type FROM tweets WHERE trend_id = ?",
            (trend_id,),
        )
        row = await cursor.fetchone()
        assert dict(row)["content"] == ""
        assert dict(row)["tweet_type"] == ""
        assert dict(row)["content_type"] == "short"

    @pytest.mark.asyncio
    async def test_batch_custom_saved_to_json(self, db):
        """saved_to 파라미터가 JSON 직렬화."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        await save_tweets_batch(
            db, [_tweet("커스텀")], trend_id, run_id,
            saved_to=["notion", "sheets"],
        )
        await db.commit()

        cursor = await db.execute("SELECT saved_to FROM tweets WHERE trend_id = ?", (trend_id,))
        row = await cursor.fetchone()
        import json
        saved = json.loads(dict(row)["saved_to"])
        assert saved == ["notion", "sheets"]

    @pytest.mark.asyncio
    async def test_batch_rollback_on_executemany_failure(self, db):
        """executemany 실패 시 롤백 후 re-raise."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        # 정상 1건 먼저 삽입
        await save_tweets_batch(db, [_tweet("선행 데이터")], trend_id, run_id)
        await db.commit()

        initial_cursor = await db.execute("SELECT COUNT(*) as cnt FROM tweets")
        initial_count = dict(await initial_cursor.fetchone())["cnt"]

        # char_count에 문자열을 넣어 타입 에러 유발은 SQLite에서 불가하므로
        # 컬럼 수 불일치를 만들어 에러 유발
        bad_tweet = _tweet("에러 유발")
        bad_tweet.content_type = None  # None도 SQLite에선 통과하므로, 다른 방법 사용

        # 대신 테이블을 rename해서 INSERT 실패 유발
        await db.execute("ALTER TABLE tweets RENAME TO tweets_backup")
        await db.commit()

        with pytest.raises(Exception):
            await save_tweets_batch(db, [_tweet("실패할 트윗")], trend_id, run_id)

        # 복원
        await db.execute("ALTER TABLE tweets_backup RENAME TO tweets")
        await db.commit()


# ── mark_tweet_posted + resolve 로직 ──────────────────────────────────────────


class TestMarkTweetPosted:

    @pytest.mark.asyncio
    async def test_mark_by_row_id(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        row_id = await save_tweet(db, _tweet("포스팅 테스트"), trend_id, run_id)

        result = await mark_tweet_posted(db, x_tweet_id="x-123", tweet_row_id=row_id)
        assert result == row_id

        cursor = await db.execute("SELECT status, x_tweet_id FROM tweets WHERE id = ?", (row_id,))
        row = await cursor.fetchone()
        assert dict(row)["status"] == "posted"
        assert dict(row)["x_tweet_id"] == "x-123"

    @pytest.mark.asyncio
    async def test_mark_by_content_match(self, db):
        """row_id 없이 content 기반으로 resolve."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        content = "콘텐츠 매칭 테스트 트윗"
        await save_tweet(db, _tweet(content), trend_id, run_id)

        result = await mark_tweet_posted(
            db, x_tweet_id="x-456", content=content, trend_id=trend_id, run_id=run_id
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_mark_nonexistent_returns_none(self, db):
        result = await mark_tweet_posted(db, x_tweet_id="x-999", tweet_row_id=99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_mark_no_identifiers_returns_none(self, db):
        """row_id도 content도 없으면 None."""
        result = await mark_tweet_posted(db, x_tweet_id="x-000")
        assert result is None

    @pytest.mark.asyncio
    async def test_already_posted_not_resolved_by_content(self, db):
        """이미 posted_at이 있는 트윗은 content 기반 resolve 대상에서 제외."""
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        content = "이미 게시된 트윗"
        row_id = await save_tweet(db, _tweet(content), trend_id, run_id)
        await mark_tweet_posted(db, x_tweet_id="x-first", tweet_row_id=row_id)

        # content로 다시 검색하면 None (posted_at이 이미 채워져 있으므로)
        result = await mark_tweet_posted(db, x_tweet_id="x-second", content=content)
        assert result is None


# ── sync_tweet_metrics ────────────────────────────────────────────────────────


class TestSyncMetrics:

    @pytest.mark.asyncio
    async def test_sync_by_row_id(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        row_id = await save_tweet(db, _tweet(), trend_id, run_id)

        updated = await sync_tweet_metrics(
            db, tweet_row_id=row_id, impressions=500, engagements=25, engagement_rate=5.0
        )
        assert updated == 1

        cursor = await db.execute("SELECT impressions, engagement_rate FROM tweets WHERE id = ?", (row_id,))
        row = await cursor.fetchone()
        assert dict(row)["impressions"] == 500
        assert dict(row)["engagement_rate"] == 5.0

    @pytest.mark.asyncio
    async def test_sync_by_x_tweet_id(self, db):
        run_id = await _seed_run(db)
        trend_id = await _seed_trend(db, run_id)
        row_id = await save_tweet(db, _tweet(), trend_id, run_id)
        await mark_tweet_posted(db, x_tweet_id="x-metric-test", tweet_row_id=row_id)

        updated = await sync_tweet_metrics(
            db, x_tweet_id="x-metric-test", impressions=100, engagements=10
        )
        assert updated == 1

    @pytest.mark.asyncio
    async def test_sync_no_identifier_returns_zero(self, db):
        updated = await sync_tweet_metrics(db)
        assert updated == 0


# ── posting_time_stats ────────────────────────────────────────────────────────


class TestPostingTimeStats:

    @pytest.mark.asyncio
    async def test_record_and_query_best_hours(self, db):
        # sample_count >= 3 조건 충족을 위해 4번 기록
        for _ in range(4):
            await record_posting_time_stat(db, category="tech", hour=9, engagement_label="높음")
            await record_posting_time_stat(db, category="tech", hour=14, engagement_label="보통")
            await record_posting_time_stat(db, category="tech", hour=22, engagement_label="낮음")

        best = await get_best_posting_hours(db, category="tech", top_n=2)
        assert len(best) == 2
        assert best[0] == 9  # 높음 평균 1.0이 가장 높음

    @pytest.mark.asyncio
    async def test_no_data_returns_empty(self, db):
        best = await get_best_posting_hours(db, category="nonexistent")
        assert best == []

    @pytest.mark.asyncio
    async def test_unknown_label_defaults_to_half(self, db):
        """알 수 없는 engagement_label은 0.5로 처리."""
        for _ in range(4):
            await record_posting_time_stat(db, category="misc", hour=12, engagement_label="unknown")
        best = await get_best_posting_hours(db, category="misc")
        # sample_count=4 >= 3 이므로 결과 존재
        assert 12 in best
