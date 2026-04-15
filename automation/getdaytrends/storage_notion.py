"""
getdaytrends — Notion Storage
Notion API 저장 + 지연 백오프 재시도 로직.
storage.py에서 분리됨.
"""

import asyncio
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger as log

# B-003 fix: fire-and-forget Task가 GC에 수거되지 않도록 강한 참조 유지용 Set
_bg_tasks: set[asyncio.Task] = set()

try:
    from .config import AppConfig
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from config import AppConfig
    from models import ScoredTrend, TweetBatch

# Notion client (optional dependency)
try:
    from notion_client import Client as NotionClient
    from notion_client.errors import APIResponseError

    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    NotionClient = None  # type: ignore
    APIResponseError = None  # type: ignore

# Notion API 재시도 대상 HTTP 상태 코드
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_MAX_RETRIES = 4
_BASE_DELAY = 1.0  # 초 (1s → 2s → 4s → 8s)

# -- notion builder imports --
try:
    from .notion_builder import (
        _build_notion_body,
        _notion_page_exists,
    )
except ImportError:
    from notion_builder import (
        _build_notion_body,
        _notion_page_exists,
    )


# ══════════════════════════════════════════════════════
#  Retry Logic
# ══════════════════════════════════════════════════════


def _retry_notion_call(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
    **kwargs: Any,
) -> Any:
    """
    Notion API 호출을 지연 백오프로 재시도.

    429 (Rate Limit), 500, 502, 503 에러 발생 시 최대 max_retries 회 재시도.
    429의 경우 Retry-After 헤더가 있으면 해당 시간만큼 대기.
    그 외 에러는 즉시 raise.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if APIResponseError is None or not isinstance(e, APIResponseError):
                raise

            status = getattr(e, "status", None)
            if status not in _RETRYABLE_STATUS_CODES:
                raise

            last_exception = e

            if attempt >= max_retries:
                log.error(f"Notion API 재시도 한도 초과 (HTTP {status}): {max_retries + 1}회 시도 후 실패")
                raise

            retry_after = None
            if status == 429:
                body = getattr(e, "body", None)
                if isinstance(body, dict):
                    retry_after = body.get("retry_after")

            if retry_after and isinstance(retry_after, (int, float)):
                delay = min(float(retry_after), 60.0)
            else:
                delay = min(base_delay * (2**attempt), 60.0)

            log.warning(
                f"Notion API 에러 (HTTP {status}), {delay:.1f}초 후 재시도 ({attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)

    if last_exception:
        raise last_exception


def _is_notion_provider_error(exc: Exception) -> bool:
    return APIResponseError is not None and isinstance(exc, APIResponseError)


def _persist_content_hub_link(config: AppConfig, draft_id: str, page_id: str, review_status: str) -> None:
    """Content Hub 페이지 ID를 SQLite draft 레코드에 연결."""
    if not draft_id:
        return
    try:
        try:
            from .db import attach_draft_to_notion_page, get_connection, init_db
        except ImportError:
            from db import attach_draft_to_notion_page, get_connection, init_db

        async def _runner() -> None:
            conn = await get_connection(config.db_path, database_url=config.database_url)
            try:
                await init_db(conn)
                await attach_draft_to_notion_page(conn, draft_id, page_id, review_status=review_status)
            finally:
                await conn.close()

        # C-04 fix: 이벤트루프 내부에서는 create_task, 외부에서는 asyncio.run
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # B-003 fix: Task 객체를 _bg_tasks에 보관하여 GC 수거 방지
            task = asyncio.ensure_future(_runner())
            _bg_tasks.add(task)

            def _on_done(t: asyncio.Task) -> None:
                _bg_tasks.discard(t)
                exc = t.exception() if not t.cancelled() else None
                if exc:
                    log.warning(f"Content Hub link persistence failed (bg): {exc}")

            task.add_done_callback(_on_done)
        else:
            asyncio.run(_runner())
    except Exception as exc:
        log.debug(f"Content Hub link persistence failed: {exc}")


# ══════════════════════════════════════════════════════
#  Legacy Korean Schema Builder
# ══════════════════════════════════════════════════════


def _build_legacy_notion_properties(
    batch: TweetBatch,
    trend: ScoredTrend,
    now: datetime,
) -> dict[str, Any]:
    """Map generated tweets to the Korean legacy Notion schema used by 🫒 Getdaytrends."""

    slots: list[tuple[str, tuple[str, ...]]] = [
        ("공감유도형", ("공감", "자조", "공감형")),
        ("꿀팁형", ("꿀팁", "실용", "팁")),
        ("찬반질문형", ("질문", "찬반", "도발")),
        ("명언형", ("명언", "데이터", "반전", "선언")),
        ("유머밈형", ("유머", "밈", "핫테이크", "관찰")),
    ]

    normalized = [(idx, (tweet.tweet_type or "").replace(" ", ""), tweet.content) for idx, tweet in enumerate(batch.tweets)]
    used_indexes: set[int] = set()
    slot_values: dict[str, str] = {}

    for slot_name, aliases in slots:
        for idx, tweet_type, content in normalized:
            if idx in used_indexes:
                continue
            if any(alias in tweet_type for alias in aliases):
                slot_values[slot_name] = content
                used_indexes.add(idx)
                break

    remaining = [content for idx, _tweet_type, content in normalized if idx not in used_indexes]
    for slot_name, _aliases in slots:
        if slot_name not in slot_values and remaining:
            slot_values[slot_name] = remaining.pop(0)

    title = f"[Trend #{trend.rank}] {batch.topic} | {now.strftime('%Y-%m-%d %H:%M')}"
    properties: dict[str, Any] = {
        "제목": {"title": [{"text": {"content": title[:200]}}]},
        "주제": {"rich_text": [{"text": {"content": batch.topic[:1900]}}]},
        "순위": {"number": trend.rank},
        "생성시각": {"date": {"start": now.isoformat()}},
        "상태": {"select": {"name": "대기중"}},
        "바이럴점수": {"number": trend.viral_potential},
    }

    for slot_name, content in slot_values.items():
        if content:
            properties[slot_name] = {"rich_text": [{"text": {"content": content[:1900]}}]}

    if batch.thread and batch.thread.tweets:
        thread_text = "\n---\n".join(batch.thread.tweets)
        properties["쓰레드"] = {"rich_text": [{"text": {"content": thread_text[:1900]}}]}

    return properties


# ══════════════════════════════════════════════════════
#  Main: save_to_notion
# ══════════════════════════════════════════════════════


def save_to_notion(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Save one trend batch into the legacy Korean-schema Notion database."""
    if not NOTION_AVAILABLE:
        log.error("notion-client package is required: pip install notion-client")
        return False

    try:
        notion = NotionClient(auth=config.notion_token)
        now = datetime.now()
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion connection failed: {type(exc).__name__}: {exc}")
        return False
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion configuration is invalid: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        if _is_notion_provider_error(exc):
            log.error(f"Notion provider error: {type(exc).__name__}: {exc}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(exc).__name__}: {exc}")
        return False

    today_str = now.strftime("%Y-%m-%d")
    try:
        notion_page_exists = _notion_page_exists(notion, config.notion_database_id, batch.topic, today_str)
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion duplicate check failed: {type(exc).__name__}: {exc}")
        return False
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion duplicate check invalid: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        if _is_notion_provider_error(exc):
            log.error(f"Notion provider error: {type(exc).__name__}: {exc}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(exc).__name__}: {exc}")
        return False
    if notion_page_exists:
        log.info(f"Notion duplicate skipped: '{batch.topic}' already exists today")
        return True

    properties = _build_legacy_notion_properties(batch, trend, now)

    try:
        body_blocks = _build_notion_body(batch, trend, "")
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion body build failed: {type(exc).__name__}: {exc}")
        return False
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion body build invalid: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        if _is_notion_provider_error(exc):
            log.error(f"Notion provider error: {type(exc).__name__}: {exc}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(exc).__name__}: {exc}")
        return False

    try:
        _retry_notion_call(
            notion.pages.create,
            parent={"database_id": config.notion_database_id},
            properties=properties,
            children=body_blocks,
        )
        title_items = properties.get("제목", {}).get("title", [])
        saved_title = title_items[0]["text"]["content"] if title_items else batch.topic
        log.info(f"Notion save complete: '{saved_title}' ({len(body_blocks)} blocks)")
        return True
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion save network error: {type(exc).__name__}: {exc}")
        return False
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion save failed: {type(exc).__name__}: {exc}")
        return False
