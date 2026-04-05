"""
DB Layer Resilience Tests — Redis 장애 graceful degradation 및
save_tweets_batch 트랜잭션 안전성 검증.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import make_scored_trend


async def _insert_run(conn, run_id: int = 1) -> int:
    """테스트용 run 레코드 삽입 (FK 만족)."""
    await conn.execute(
        "INSERT INTO runs (id, run_uuid, started_at, country) VALUES (?, ?, ?, ?)",
        (run_id, str(uuid.uuid4()), datetime.now().isoformat(), "korea"),
    )
    await conn.commit()
    return run_id


# ── trend_repository: Redis 장애 시 DB fallback ──────────────────────────────


class TestIsDuplicateTrendRedisResilience:
    """is_duplicate_trend가 Redis 장애 시 crash하지 않고 DB fallback하는지 검증."""

    @pytest.mark.asyncio
    async def test_redis_exists_error_falls_back_to_db(self, memory_db):
        """Redis.exists()가 예외를 던져도 DB 조회로 fallback하여 False 반환."""
        from db_layer.trend_repository import is_duplicate_trend, save_trend

        # DB에 트렌드가 없으므로 False 기대
        failing_cache = AsyncMock()
        failing_cache.exists = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("db_layer.trend_repository._get_cache_client", return_value=failing_cache), \
             patch("db_layer.trend_repository._redis_enabled", return_value=True):
            result = await is_duplicate_trend(memory_db, "AI뉴스", 50000)

        assert result is False

    @pytest.mark.asyncio
    async def test_redis_exists_error_but_db_has_dup(self, memory_db):
        """Redis 장애여도 DB에 중복이 있으면 True 반환."""
        from db_layer.trend_repository import is_duplicate_trend, save_trend

        await _insert_run(memory_db, run_id=1)
        trend = make_scored_trend(keyword="AI뉴스")
        trend.volume_last_24h = 50000
        await save_trend(memory_db, trend, run_id=1, bucket=5000)
        await memory_db.commit()

        failing_cache = AsyncMock()
        failing_cache.exists = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("db_layer.trend_repository._get_cache_client", return_value=failing_cache), \
             patch("db_layer.trend_repository._redis_enabled", return_value=True):
            result = await is_duplicate_trend(memory_db, "AI뉴스", 50000)

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_set_error_on_cache_write_is_silent(self, memory_db):
        """중복 감지 후 cache.set() 실패 시에도 True를 정상 반환."""
        from db_layer.trend_repository import is_duplicate_trend, save_trend

        await _insert_run(memory_db, run_id=1)
        trend = make_scored_trend(keyword="블록체인")
        trend.volume_last_24h = 30000
        await save_trend(memory_db, trend, run_id=1, bucket=5000)
        await memory_db.commit()

        failing_cache = AsyncMock()
        failing_cache.exists = AsyncMock(return_value=False)
        failing_cache.set = AsyncMock(side_effect=ConnectionError("Redis write failed"))

        with patch("db_layer.trend_repository._get_cache_client", return_value=failing_cache), \
             patch("db_layer.trend_repository._redis_enabled", return_value=True):
            result = await is_duplicate_trend(memory_db, "블록체인", 30000)

        assert result is True


class TestGetCachedScoreRedisResilience:
    """get_cached_score가 Redis 장애/오염 데이터에서도 DB fallback하는지 검증."""

    @pytest.mark.asyncio
    async def test_redis_get_error_falls_back_to_db(self, memory_db):
        """Redis.get() 예외 시 DB 조회 fallback."""
        from db_layer.trend_repository import get_cached_score, save_trend

        await _insert_run(memory_db, run_id=1)
        trend = make_scored_trend(keyword="테스트키워드")
        trend.volume_last_24h = 10000
        await save_trend(memory_db, trend, run_id=1, bucket=5000)
        await memory_db.commit()

        # fingerprint 계산
        from db_layer import compute_fingerprint
        fp = compute_fingerprint("테스트키워드", 10000, 5000)

        failing_cache = AsyncMock()
        failing_cache.get = AsyncMock(side_effect=TimeoutError("Redis timeout"))

        with patch("db_layer.trend_repository._get_cache_client", return_value=failing_cache), \
             patch("db_layer.trend_repository._redis_enabled", return_value=True):
            result = await get_cached_score(memory_db, fp)

        assert result is not None
        assert result["keyword"] == "테스트키워드"

    @pytest.mark.asyncio
    async def test_corrupted_cache_type_falls_back_to_db(self, memory_db):
        """캐시에 dict가 아닌 타입이 저장된 경우 DB에서 재조회."""
        from db_layer.trend_repository import get_cached_score, save_trend
        from db_layer import compute_fingerprint

        await _insert_run(memory_db, run_id=1)
        trend = make_scored_trend(keyword="오염테스트")
        trend.volume_last_24h = 20000
        await save_trend(memory_db, trend, run_id=1, bucket=5000)
        await memory_db.commit()

        fp = compute_fingerprint("오염테스트", 20000, 5000)

        # 캐시에 string이 저장된 오염 상태
        corrupted_cache = AsyncMock()
        corrupted_cache.get = AsyncMock(return_value="not-a-dict")

        with patch("db_layer.trend_repository._get_cache_client", return_value=corrupted_cache), \
             patch("db_layer.trend_repository._redis_enabled", return_value=True):
            result = await get_cached_score(memory_db, fp)

        assert result is not None
        assert isinstance(result, dict)
        assert result["keyword"] == "오염테스트"


# ── tweet_repository: save_tweets_batch 트랜잭션 안전성 ──────────────────────


class TestSaveTweetsBatchResilience:
    """save_tweets_batch의 빈 리스트 방어 및 에러 시 롤백 검증."""

    @pytest.mark.asyncio
    async def test_empty_list_is_noop(self, memory_db):
        """빈 리스트 전달 시 DB에 아무것도 쓰지 않음."""
        from db_layer.tweet_repository import save_tweets_batch

        await save_tweets_batch(memory_db, [], trend_id=1, run_id=1)

        cursor = await memory_db.execute("SELECT COUNT(*) as cnt FROM tweets")
        row = await cursor.fetchone()
        assert row["cnt"] == 0

    @pytest.mark.asyncio
    async def test_db_error_raises_after_rollback(self, memory_db):
        """executemany 실패 시 예외가 상위로 전파됨 (silent failure 방지)."""
        from db_layer.tweet_repository import save_tweets_batch

        # content가 없는 잘못된 객체 — executemany가 실패하도록 유도
        class BadTweet:
            pass

        bad_tweets = [BadTweet()]
        # getattr fallback으로 빈 문자열이 들어가므로 직접 executemany를 깨뜨리기 위해
        # conn을 mock
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock(side_effect=Exception("DB write failed"))
        mock_conn.rollback = AsyncMock()

        with pytest.raises(Exception, match="DB write failed"):
            await save_tweets_batch(mock_conn, bad_tweets, trend_id=1, run_id=1)

        mock_conn.rollback.assert_called_once()


# ── tweet_repository: get_cached_content Redis resilience ────────────────────


class TestGetCachedContentRedisResilience:
    """get_cached_content가 Redis 장애 시 DB fallback하는지 검증."""

    @pytest.mark.asyncio
    async def test_redis_error_falls_back_to_db(self, memory_db):
        """Redis.get() 실패 시 DB 조회 fallback, None 반환 (데이터 없음)."""
        from db_layer.tweet_repository import get_cached_content

        failing_cache = AsyncMock()
        failing_cache.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("db_layer.tweet_repository._get_cache_client", return_value=failing_cache), \
             patch("db_layer.tweet_repository._redis_enabled", return_value=True):
            result = await get_cached_content(memory_db, "nonexistent_fp")

        assert result is None  # DB에도 없으므로 None

    @pytest.mark.asyncio
    async def test_corrupted_cache_type_falls_back_to_db(self, memory_db):
        """캐시에 list가 아닌 타입이 저장된 경우 DB에서 재조회."""
        from db_layer.tweet_repository import get_cached_content

        corrupted_cache = AsyncMock()
        corrupted_cache.get = AsyncMock(return_value="not-a-list")

        with patch("db_layer.tweet_repository._get_cache_client", return_value=corrupted_cache), \
             patch("db_layer.tweet_repository._redis_enabled", return_value=True):
            result = await get_cached_content(memory_db, "some_fp")

        assert result is None  # DB에도 없으므로 None
