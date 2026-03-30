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

# ── Path priority ───────────────────────────────────────────────────────────


def pytest_configure(config):
    pkg_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    workspace_root = os.path.normpath(os.path.join(pkg_root, ".."))
    notebooklm_src = os.path.normpath(os.path.join(pkg_root, "..", "notebooklm-automation", "src"))
    # Remove any existing entry first, then insert at front
    for p in (pkg_root, workspace_root):
        while p in sys.path:
            sys.path.remove(p)
    sys.path.insert(0, pkg_root)
    sys.path.insert(1, workspace_root)
    if os.path.isdir(notebooklm_src):
        while notebooklm_src in sys.path:
            sys.path.remove(notebooklm_src)
        sys.path.insert(2, notebooklm_src)

    # loguru 기본 핸들러 제거 후 lambda sink 추가:
    # pytest stdout/stderr 캡처와 충돌로 발생하는
    # "ValueError: I/O operation on closed file" 방지.
    try:
        from loguru import logger

        logger.remove()  # 기본 stderr 핸들러 제거
        logger.add(lambda _: None, level="WARNING")  # no-op null sink
    except ImportError:
        pass


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


@pytest.fixture
async def memory_db():
    """인메모리 SQLite 연결 (테스트 격리)."""
    from db import get_connection, init_db

    db = await get_connection(":memory:")
    await init_db(db)
    yield db
    await db.close()


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
