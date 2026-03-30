"""
getdaytrends v3.0 - E2E 파이프라인 테스트
Mock LLM + 인메모리 DB로 전체 수집→스코어링→생성→저장 흐름 검증.
실제 API 호출 없이 파이프라인 계약(contract)을 보장.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from config import AppConfig
from db import db_transaction, get_connection, init_db, save_run
from models import (
    GeneratedTweet,
    MultiSourceContext,
    RawTrend,
    RunResult,
    ScoredTrend,
    TrendSource,
    TweetBatch,
)

# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════


@pytest.fixture
def config() -> AppConfig:
    cfg = AppConfig()
    cfg.storage_type = "none"
    cfg.dry_run = True
    cfg.enable_clustering = False
    cfg.enable_long_form = False
    cfg.enable_threads = False
    cfg.enable_sentiment_filter = True
    cfg.cache_volume_bucket = 5000
    cfg.notion_sem_limit = 3
    return cfg


@pytest.fixture
async def conn():
    """인메모리 SQLite 연결 (테스트 격리)."""
    db = await get_connection(":memory:")
    await init_db(db)
    yield db
    await db.close()


def _make_raw_trend(name: str, volume: int = 10000) -> RawTrend:
    return RawTrend(
        name=name,
        source=TrendSource.GETDAYTRENDS,
        volume=str(volume),
        volume_numeric=volume,
        country="korea",
    )


def _make_scored_trend(keyword: str, viral: int = 75, safety: bool = False) -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral,
        trend_acceleration="+5%",
        top_insight="테스트 인사이트",
        suggested_angles=["앵글1", "앵글2"],
        best_hook_starter="최고의 훅",
        context=MultiSourceContext(twitter_insight="X 반응", reddit_insight="Reddit 반응"),
        safety_flag=safety,
        sentiment="harmful" if safety else "neutral",
    )


def _make_batch(topic: str) -> TweetBatch:
    return TweetBatch(
        topic=topic,
        tweets=[
            GeneratedTweet(tweet_type="공감 유도형", content="테스트 트윗 내용입니다.", content_type="short"),
            GeneratedTweet(tweet_type="꿀팁형", content="꿀팁 트윗입니다.", content_type="short"),
        ],
        viral_score=75,
    )


# ══════════════════════════════════════════════════════
#  DB 트랜잭션 테스트
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_db_transaction_commit(conn):
    """정상 실행 시 트랜잭션이 commit되는지 확인."""
    from db import save_trend

    run = RunResult(run_id="test-run-1", country="korea")
    run_id = await save_run(conn, run)

    trend = _make_scored_trend("테스트트렌드")
    async with db_transaction(conn):
        trend_id = await save_trend(conn, trend, run_id)

    # commit 확인: 레코드가 존재해야 함
    cursor = await conn.execute("SELECT id, keyword FROM trends WHERE id = ?", (trend_id,))
    row = await cursor.fetchone()
    assert row is not None
    assert row["keyword"] == "테스트트렌드"


@pytest.mark.asyncio
async def test_db_transaction_rollback(conn):
    """예외 발생 시 트랜잭션이 rollback되는지 확인."""
    from db import save_trend

    run = RunResult(run_id="test-run-2", country="korea")
    run_id = await save_run(conn, run)
    trend = _make_scored_trend("롤백테스트")

    before_cursor = await conn.execute("SELECT COUNT(*) as cnt FROM trends")
    before_count = (await before_cursor.fetchone())["cnt"]

    with pytest.raises(ValueError):
        async with db_transaction(conn):
            await save_trend(conn, trend, run_id)
            raise ValueError("의도적 롤백 테스트")

    after_cursor = await conn.execute("SELECT COUNT(*) as cnt FROM trends")
    after_count = (await after_cursor.fetchone())["cnt"]
    assert after_count == before_count  # rollback으로 변경 없음


# ══════════════════════════════════════════════════════
#  safety_flag 스킵 테스트
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_step_save_skips_safety_flagged(conn, config):
    """safety_flag=True 트렌드는 저장 없이 스킵되고 run.errors에 기록."""
    from core.pipeline_steps import _step_save

    run = RunResult(run_id="test-run-3", country="korea")
    run_id = await save_run(conn, run)

    harmful_trend = _make_scored_trend("재난사고", viral=80, safety=True)
    normal_trend = _make_scored_trend("정상트렌드", viral=75, safety=False)

    quality_trends = [harmful_trend, normal_trend]
    batch_results = [_make_batch("재난사고"), _make_batch("정상트렌드")]

    success = await _step_save(quality_trends, batch_results, config, conn, run, run_id)

    assert success == 1  # 정상 트렌드만 저장
    assert any("safety_flag" in e for e in run.errors)

    cursor = await conn.execute("SELECT keyword FROM trends")
    saved_keywords = [row["keyword"] async for row in cursor]
    assert "재난사고" not in saved_keywords
    assert "정상트렌드" in saved_keywords


# ══════════════════════════════════════════════════════
#  배치 스코어링 테스트
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_batch_scoring_returns_correct_count(conn):
    """_batch_score_async가 입력 수만큼 ScoredTrend를 반환하는지 확인."""
    from analyzer import _batch_score_async

    raw = [_make_raw_trend(f"트렌드{i}", volume=(i + 1) * 10000) for i in range(5)]
    pairs = [(r, MultiSourceContext()) for r in raw]

    llm_response = json.dumps(
        [
            {
                "keyword": r.name,
                "volume_last_24h": r.volume_numeric,
                "trend_acceleration": "+5%",
                "viral_potential": 70 + i,
                "top_insight": f"인사이트{i}",
                "suggested_angles": ["앵글1"],
                "best_hook_starter": "훅",
                "category": "테크",
                "sentiment": "neutral",
                "safety_flag": False,
            }
            for i, r in enumerate(raw)
        ]
    )

    mock_response = MagicMock()
    mock_response.text = llm_response
    mock_client = MagicMock()
    mock_client.acreate = AsyncMock(return_value=mock_response)

    results = await _batch_score_async(pairs, mock_client, conn)
    assert len(results) == 5
    for r in results:
        assert 0 <= r.viral_potential <= 100
        assert r.sentiment in ("positive", "neutral", "negative", "harmful")


@pytest.mark.asyncio
async def test_batch_scoring_fallback_on_parse_error(conn):
    """배치 응답 파싱 실패 시 개별 폴백이 동작하는지 확인."""
    from analyzer import _batch_score_async

    raw = [_make_raw_trend("폴백테스트", volume=5000)]
    pairs = [(raw[0], MultiSourceContext())]

    # 배치 응답을 깨뜨린 후 개별 스코어링 mock
    bad_response = MagicMock()
    bad_response.text = "invalid json"

    good_response = MagicMock()
    good_response.text = json.dumps(
        {
            "keyword": "폴백테스트",
            "volume_last_24h": 5000,
            "trend_acceleration": "+0%",
            "viral_potential": 65,
            "top_insight": "폴백 인사이트",
            "suggested_angles": [],
            "best_hook_starter": "훅",
            "category": "기타",
            "sentiment": "neutral",
            "safety_flag": False,
        }
    )

    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        return bad_response if call_count <= 2 else good_response

    mock_client = MagicMock()
    mock_client.acreate = AsyncMock(side_effect=_side_effect)

    results = await _batch_score_async(pairs, mock_client, conn)
    assert len(results) == 1
    # 폴백이든 기본값이든 ScoredTrend를 반환해야 함
    assert results[0].keyword == "폴백테스트"


# ══════════════════════════════════════════════════════
#  db_transaction 후 tweet variant_id/language 저장 테스트
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_save_tweets_with_variant_and_language(conn):
    """v3.0 신규 컬럼 variant_id, language가 정상 저장되는지 확인."""
    from db import save_trend, save_tweets_batch

    run = RunResult(run_id="test-run-4", country="korea")
    run_id = await save_run(conn, run)
    trend = _make_scored_trend("언어테스트")

    async with db_transaction(conn):
        trend_id = await save_trend(conn, trend, run_id)
        tweets = [
            GeneratedTweet(tweet_type="공감형", content="A 변형", content_type="short", variant_id="A", language="ko"),
            GeneratedTweet(
                tweet_type="공감형", content="B variant", content_type="short", variant_id="B", language="en"
            ),
        ]
        await save_tweets_batch(conn, tweets, trend_id, run_id)

    cursor = await conn.execute("SELECT tweet_type, variant_id, language FROM tweets WHERE trend_id = ?", (trend_id,))
    rows = [dict(r) for r in await cursor.fetchall()]
    assert len(rows) == 2
    variant_ids = {r["variant_id"] for r in rows}
    languages = {r["language"] for r in rows}
    assert "A" in variant_ids and "B" in variant_ids
    assert "ko" in languages and "en" in languages


# ══════════════════════════════════════════════════════
#  compute_fingerprint bucket 파라미터 테스트
# ══════════════════════════════════════════════════════


def test_fingerprint_bucket_affects_result():
    """bucket 크기가 다르면 다른 핑거프린트가 나와야 함."""
    from db import compute_fingerprint

    fp_5k = compute_fingerprint("트렌드", 47000, bucket=5000)
    fp_1k = compute_fingerprint("트렌드", 47000, bucket=1000)
    fp_10k = compute_fingerprint("트렌드", 47000, bucket=10000)

    # 45000(5k 버킷) vs 47000(1k 버킷=47000) vs 40000(10k 버킷) → 모두 달라야 함
    assert fp_5k != fp_1k
    assert fp_5k != fp_10k


def test_fingerprint_same_bucket_same_result():
    """같은 bucket 내 볼륨은 동일 핑거프린트를 반환."""
    from db import compute_fingerprint

    fp1 = compute_fingerprint("동일트렌드", 45000, bucket=5000)
    fp2 = compute_fingerprint("동일트렌드", 47000, bucket=5000)
    # 45000//5000*5000=45000, 47000//5000*5000=45000 → 동일
    assert fp1 == fp2
