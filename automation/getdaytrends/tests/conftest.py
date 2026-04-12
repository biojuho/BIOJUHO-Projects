"""
getdaytrends pytest configuration & shared fixture factories.

1. Ensures the getdaytrends package root takes priority on sys.path so that
   ``from models import ...`` resolves to getdaytrends/models.py, not
   biolinker/models.py when tests run from the workspace root.
2. Suppresses loguru I/O errors during pytest capture.
3. Provides shared fixture factories (config, trend builders, mock LLM client,
   in-memory DB) so individual test modules don't repeat boilerplate.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# ── Path priority ───────────────────────────────────────────────────────────


def pytest_configure(config):
    pkg_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    notebooklm_src = os.path.normpath(os.path.join(pkg_root, "..", "notebooklm-automation", "src"))
    # Ensure getdaytrends package root takes priority for bare 'core', 'models' etc.
    while pkg_root in sys.path:
        sys.path.remove(pkg_root)
    sys.path.insert(0, pkg_root)
    if os.path.isdir(notebooklm_src):
        while notebooklm_src in sys.path:
            sys.path.remove(notebooklm_src)
        sys.path.insert(1, notebooklm_src)

    # loguru 기본 핸들러 제거 후 lambda sink 추가:
    # pytest stdout/stderr 캡처와 충돌로 발생하는
    # "ValueError: I/O operation on closed file" 방지.
    try:
        from loguru import logger

        logger.remove()  # 기본 stderr 핸들러 제거
        logger.add(lambda _: None, level="WARNING")  # no-op null sink
    except ImportError:
        pass


def pytest_runtest_setup(item):
    """Reset the *system* default event loop before any fixture setup.

    FastAPI TestClient and other sync-wrapper code call
    ``asyncio.get_event_loop()`` during import / startup.  If a previous
    pytest-asyncio test closed that loop, the system default is stale.
    This hook fires before fixture resolution, so the loop is always
    available.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


@pytest.fixture(autouse=True)
def isolate_database_url():
    """Keep workspace DATABASE_URL from leaking into SQLite-focused tests."""
    original = os.environ.pop("DATABASE_URL", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["DATABASE_URL"] = original


@pytest.fixture
def event_loop():
    """Override default event_loop fixture to always provide a fresh loop.

    On Python 3.14+, pytest-asyncio may reuse a closed event loop from
    prior test functions.  Creating a new loop per test function prevents
    'RuntimeError: Event loop is closed' cascade failures.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    # Immediately replace with a fresh loop so the *next* test's
    # hook / fixture / TestClient can find an open default loop.
    asyncio.set_event_loop(asyncio.new_event_loop())


@pytest.fixture(autouse=True)
def _reset_pg_pool():
    """Prevent asyncpg connection pool leakage between tests.

    Some tests (test_db_schema_pg, test_dashboard) mock or set _PG_POOL /
    DATABASE_URL.  Without cleanup, subsequent tests that call
    get_connection(\":memory:\") may get routed to a real or mock asyncpg
    pool instead of aiosqlite.
    """
    import os
    import db_layer.connection as _dbconn

    _dbconn._PG_POOL = None
    old_url = os.environ.pop("DATABASE_URL", None)
    yield
    _dbconn._PG_POOL = None
    if old_url is not None:
        os.environ["DATABASE_URL"] = old_url
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture(autouse=True)
def reset_notebooklm_config():
    try:
        from notebooklm_automation.config import reset_config
    except ImportError:
        yield
        return

    reset_config()
    yield
    reset_config()


# ── Lazy imports (after path is fixed) ──────────────────────────────────────
# These are imported lazily inside fixtures to avoid import-time failures
# when conftest is loaded before sys.path is configured.


# ── Config fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def test_config():
    """테스트용 AppConfig — 외부 저장/네트워크 비활성화."""
    from config import AppConfig

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


# ── In-memory DB fixture ───────────────────────────────────────────────────


@pytest_asyncio.fixture
async def memory_db():
    """인메모리 SQLite 연결 (테스트 격리).

    Guard: clear any leaked _PG_POOL and DATABASE_URL so get_connection
    always returns an aiosqlite connection, even when prior tests (e.g.
    test_dashboard / test_db_schema_pg) leave module-level state behind.
    """
    import os
    import db_layer.connection as _dbconn

    _dbconn._PG_POOL = None
    old_url = os.environ.pop("DATABASE_URL", None)

    from db import get_connection, init_db

    db = await get_connection(":memory:")
    await init_db(db)
    yield db
    await db.close()

    # Restore DATABASE_URL if it was set
    if old_url is not None:
        os.environ["DATABASE_URL"] = old_url


# ── Trend / Batch factory functions ─────────────────────────────────────────
# These are plain functions, not fixtures, so tests can call them with args.


def make_raw_trend(name: str = "테스트트렌드", volume: int = 10000):
    """RawTrend factory with sensible defaults."""
    from models import RawTrend, TrendSource

    return RawTrend(
        name=name,
        source=TrendSource.GETDAYTRENDS,
        volume=str(volume),
        volume_numeric=volume,
        country="korea",
    )


def make_scored_trend(
    keyword: str = "테스트트렌드",
    viral: int = 75,
    safety: bool = False,
    acc: str = "+5%",
):
    """ScoredTrend factory with sensible defaults."""
    from models import MultiSourceContext, ScoredTrend

    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral,
        trend_acceleration=acc,
        top_insight="테스트 인사이트",
        suggested_angles=["앵글1", "앵글2"],
        best_hook_starter="최고의 훅",
        context=MultiSourceContext(twitter_insight="X 반응", reddit_insight="Reddit 반응"),
        safety_flag=safety,
        sentiment="harmful" if safety else "neutral",
    )


def make_batch(topic: str = "테스트트렌드", viral_score: int = 75):
    """TweetBatch factory with sensible defaults."""
    from models import GeneratedTweet, TweetBatch

    return TweetBatch(
        topic=topic,
        tweets=[
            GeneratedTweet(
                tweet_type="공감 유도형",
                content="테스트 트윗 내용입니다.",
                content_type="short",
            ),
            GeneratedTweet(
                tweet_type="꿀팁형",
                content="꿀팁 트윗입니다.",
                content_type="short",
            ),
        ],
        viral_score=viral_score,
    )


# ── Mock LLM client fixture ────────────────────────────────────────────────


@pytest.fixture
def mock_llm_client():
    """MagicMock LLM client with `acreate` returning a configurable response.

    Usage in tests::

        def test_something(mock_llm_client):
            mock_llm_client.response_text = '{"key": "value"}'
            result = some_function(mock_llm_client.client)
    """
    response = MagicMock()
    response.text = "{}"
    client = MagicMock()
    client.acreate = AsyncMock(return_value=response)

    class _MockLLM:
        def __init__(self):
            self.client = client
            self.response = response

        @property
        def response_text(self):
            return self.response.text

        @response_text.setter
        def response_text(self, value: str):
            self.response.text = value
            self.client.acreate = AsyncMock(return_value=self.response)

    return _MockLLM()
