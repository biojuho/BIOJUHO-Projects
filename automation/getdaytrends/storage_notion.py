"""
getdaytrends — Notion Storage
Notion API 저장 + 지연 백오프 재시도 로직.
storage.py에서 분리됨.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
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

_LEGACY_REQUIRED_PROPERTIES = (
    "제목",
    "주제",
    "순위",
    "생성시각",
    "상태",
    "바이럴점수",
)


@dataclass(frozen=True)
class NotionWriteTarget:
    """Resolved Notion write target for old database IDs and new data source IDs."""

    configured_id: str
    write_id: str
    parent: dict[str, str]
    schema: dict[str, Any]
    uses_data_source: bool

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
    """Call Notion with bounded retries for retryable provider errors."""
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_retryable_notion_error(exc):
                raise

            status = getattr(exc, "status", None)
            last_exception = exc

            if attempt >= max_retries:
                log.error(f"Notion API retry limit exceeded (HTTP {status}): {max_retries + 1} attempts failed")
                raise

            delay = _retry_delay(exc, attempt=attempt, base_delay=base_delay)
            log.warning(f"Notion API error (HTTP {status}), retrying in {delay:.1f}s ({attempt + 1}/{max_retries})...")
            time.sleep(delay)

    if last_exception:
        raise last_exception


def _is_retryable_notion_error(exc: Exception) -> bool:
    if APIResponseError is None or not isinstance(exc, APIResponseError):
        return False
    return getattr(exc, "status", None) in _RETRYABLE_STATUS_CODES


def _retry_delay(exc: Exception, *, attempt: int, base_delay: float) -> float:
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None:
        return min(retry_after, 60.0)
    return min(base_delay * (2**attempt), 60.0)


def _retry_after_seconds(exc: Exception) -> float | None:
    if getattr(exc, "status", None) != 429:
        return None
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None
    retry_after = body.get("retry_after")
    return float(retry_after) if isinstance(retry_after, (int, float)) else None


def _is_notion_provider_error(exc: Exception) -> bool:
    return APIResponseError is not None and isinstance(exc, APIResponseError)


def _first_data_source_id(database_payload: dict[str, Any]) -> str:
    data_sources = database_payload.get("data_sources") or []
    if not data_sources:
        return ""
    first = data_sources[0]
    return first.get("id", "") if isinstance(first, dict) else ""


def _has_data_sources_endpoint(notion: Any) -> bool:
    endpoint = getattr(notion, "data_sources", None)
    return endpoint is not None and callable(getattr(endpoint, "retrieve", None))


def _legacy_parent(database_id: str, schema: dict[str, Any] | None = None) -> NotionWriteTarget:
    return NotionWriteTarget(
        configured_id=database_id,
        write_id=database_id,
        parent={"database_id": database_id},
        schema=schema or {},
        uses_data_source=False,
    )


def _data_source_parent(configured_id: str, data_source_id: str, schema: dict[str, Any] | None = None) -> NotionWriteTarget:
    return NotionWriteTarget(
        configured_id=configured_id,
        write_id=data_source_id,
        parent={"type": "data_source_id", "data_source_id": data_source_id},
        schema=schema or {},
        uses_data_source=True,
    )


def _retrieve_data_source_target(notion: Any, configured_id: str, data_source_id: str) -> NotionWriteTarget | None:
    if not data_source_id or not _has_data_sources_endpoint(notion):
        return None
    data_source = _retry_notion_call(notion.data_sources.retrieve, data_source_id=data_source_id)
    schema = data_source.get("properties", {}) if isinstance(data_source, dict) else {}
    return _data_source_parent(configured_id, data_source_id, schema)


def _resolve_notion_write_target(notion: Any, configured_id: str) -> NotionWriteTarget | None:
    """Resolve a configured Notion database/data source ID into a write target."""
    if not configured_id:
        return None

    try:
        database = _retry_notion_call(notion.databases.retrieve, database_id=configured_id)
    except Exception as database_exc:
        try:
            target = _retrieve_data_source_target(notion, configured_id, configured_id)
            if target is not None:
                return target
        except Exception:
            pass
        _log_notion_exception("Notion database/data source lookup failed", database_exc)
        return None

    if not isinstance(database, dict):
        return _legacy_parent(configured_id)

    data_source_id = _first_data_source_id(database)
    if data_source_id:
        try:
            target = _retrieve_data_source_target(notion, configured_id, data_source_id)
            if target is not None:
                return target
        except Exception as exc:
            _log_notion_exception("Notion data source lookup failed", exc)
            return None

    return _legacy_parent(configured_id, database.get("properties", {}) or {})


def _missing_legacy_notion_properties(schema: dict[str, Any]) -> list[str]:
    return [name for name in _LEGACY_REQUIRED_PROPERTIES if name not in schema]


def _query_notion_target(notion: Any, target: NotionWriteTarget, **kwargs: Any) -> dict[str, Any]:
    if target.uses_data_source and callable(getattr(getattr(notion, "data_sources", None), "query", None)):
        return _retry_notion_call(notion.data_sources.query, data_source_id=target.write_id, **kwargs)
    return _retry_notion_call(notion.databases.query, database_id=target.write_id, **kwargs)


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


def _legacy_notion_slots() -> list[tuple[str, tuple[str, ...]]]:
    return [
        ("공감유도형", ("공감", "자조", "공감형")),
        ("꿀팁형", ("꿀팁", "실용", "팁")),
        ("찬반질문형", ("질문", "찬반", "도발")),
        ("명언형", ("명언", "데이터", "반전", "선언")),
        ("유머밈형", ("유머", "밈", "핫테이크", "관찰")),
    ]


def _normalized_tweets(batch: TweetBatch) -> list[tuple[int, str, str]]:
    return [(idx, (tweet.tweet_type or "").replace(" ", ""), tweet.content) for idx, tweet in enumerate(batch.tweets)]


def _matching_legacy_slot(
    aliases: tuple[str, ...],
    normalized: list[tuple[int, str, str]],
    used_indexes: set[int],
) -> tuple[int, str] | None:
    for idx, tweet_type, content in normalized:
        if idx not in used_indexes and any(alias in tweet_type for alias in aliases):
            return idx, content
    return None


def _fill_legacy_slots_by_alias(
    slots: list[tuple[str, tuple[str, ...]]],
    normalized: list[tuple[int, str, str]],
) -> tuple[dict[str, str], set[int]]:
    used_indexes: set[int] = set()
    slot_values: dict[str, str] = {}
    for slot_name, aliases in slots:
        match = _matching_legacy_slot(aliases, normalized, used_indexes)
        if match:
            idx, content = match
            slot_values[slot_name] = content
            used_indexes.add(idx)
    return slot_values, used_indexes


def _fill_remaining_legacy_slots(
    slot_values: dict[str, str],
    slots: list[tuple[str, tuple[str, ...]]],
    normalized: list[tuple[int, str, str]],
    used_indexes: set[int],
) -> None:
    remaining = [content for idx, _tweet_type, content in normalized if idx not in used_indexes]
    for slot_name, _aliases in slots:
        if slot_name not in slot_values and remaining:
            slot_values[slot_name] = remaining.pop(0)


def _legacy_slot_values(batch: TweetBatch) -> dict[str, str]:
    slots = _legacy_notion_slots()
    normalized = _normalized_tweets(batch)
    slot_values, used_indexes = _fill_legacy_slots_by_alias(slots, normalized)
    _fill_remaining_legacy_slots(slot_values, slots, normalized, used_indexes)
    return slot_values


def _base_legacy_properties(batch: TweetBatch, trend: ScoredTrend, now: datetime) -> dict[str, Any]:
    title = f"[Trend #{trend.rank}] {batch.topic} | {now.strftime('%Y-%m-%d %H:%M')}"
    return {
        "제목": {"title": [{"text": {"content": title[:200]}}]},
        "주제": {"rich_text": [{"text": {"content": batch.topic[:1900]}}]},
        "순위": {"number": trend.rank},
        "생성시각": {"date": {"start": now.isoformat()}},
        "상태": {"select": {"name": "대기중"}},
        "바이럴점수": {"number": trend.viral_potential},
    }


def _add_legacy_slot_properties(properties: dict[str, Any], slot_values: dict[str, str]) -> None:
    for slot_name, content in slot_values.items():
        if content:
            properties[slot_name] = {"rich_text": [{"text": {"content": content[:1900]}}]}


def _add_legacy_thread_property(properties: dict[str, Any], batch: TweetBatch) -> None:
    if batch.thread and batch.thread.tweets:
        thread_text = "\n---\n".join(batch.thread.tweets)
        properties["쓰레드"] = {"rich_text": [{"text": {"content": thread_text[:1900]}}]}


def _build_legacy_notion_properties(
    batch: TweetBatch,
    trend: ScoredTrend,
    now: datetime,
) -> dict[str, Any]:
    """Map generated tweets to the Korean legacy Notion schema used by Getdaytrends."""
    properties = _base_legacy_properties(batch, trend, now)
    _add_legacy_slot_properties(properties, _legacy_slot_values(batch))
    _add_legacy_thread_property(properties, batch)
    return properties

#  Main: save_to_notion
# ══════════════════════════════════════════════════════


def _log_notion_exception(phase: str, exc: Exception, *, provider_message: str = "Notion provider error") -> None:
    if _is_notion_provider_error(exc):
        log.error(f"{provider_message}: {type(exc).__name__}: {exc}")
    else:
        log.error(f"{phase}: {type(exc).__name__}: {exc}")


def _create_notion_client(config: AppConfig) -> object:
    try:
        return NotionClient(auth=config.notion_token), datetime.now()
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion connection failed: {type(exc).__name__}: {exc}")
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion configuration is invalid: {type(exc).__name__}: {exc}")
    except Exception as exc:
        _log_notion_exception("Notion sync failed unexpectedly", exc)
    return None, None


def _legacy_page_exists_today(notion, target: NotionWriteTarget, topic: str, now: datetime) -> bool | None:
    try:
        if not target.uses_data_source:
            return _notion_page_exists(notion, target.write_id, topic, now.strftime("%Y-%m-%d"))
        results = _query_notion_target(
            notion,
            target,
            filter={
                "and": [
                    {"property": "주제", "rich_text": {"contains": topic}},
                    {"property": "생성시각", "date": {"on_or_after": f"{now.strftime('%Y-%m-%d')}T00:00:00"}},
                ]
            },
            page_size=1,
        )
        return bool(results.get("results", [])) if isinstance(results, dict) else False
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion duplicate check failed: {type(exc).__name__}: {exc}")
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion duplicate check invalid: {type(exc).__name__}: {exc}")
    except Exception as exc:
        _log_notion_exception("Notion sync failed unexpectedly", exc)
    return None


def _build_legacy_page_payload(batch: TweetBatch, trend: ScoredTrend, now: datetime) -> tuple[dict, list[dict]] | None:
    properties = _build_legacy_notion_properties(batch, trend, now)
    try:
        return properties, _build_notion_body(batch, trend, "")
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion body build failed: {type(exc).__name__}: {exc}")
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion body build invalid: {type(exc).__name__}: {exc}")
    except Exception as exc:
        _log_notion_exception("Notion sync failed unexpectedly", exc)
    return None


def _saved_legacy_title(properties: dict, fallback_topic: str) -> str:
    title_items = properties.get("제목", {}).get("title", [])
    return title_items[0]["text"]["content"] if title_items else fallback_topic


def _create_legacy_notion_page(notion, target: NotionWriteTarget, properties: dict, body_blocks: list[dict], topic: str) -> bool:
    try:
        _retry_notion_call(
            notion.pages.create,
            parent=target.parent,
            properties=properties,
            children=body_blocks,
        )
        log.info(f"Notion save complete: '{_saved_legacy_title(properties, topic)}' ({len(body_blocks)} blocks)")
        return True
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Notion save network error: {type(exc).__name__}: {exc}")
    except (ValueError, RuntimeError) as exc:
        log.error(f"Notion save failed: {type(exc).__name__}: {exc}")
    return False


def save_to_notion(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Save one trend batch into the legacy Korean-schema Notion database."""
    if not NOTION_AVAILABLE:
        log.error("notion-client package is required: pip install notion-client")
        return False

    notion, now = _create_notion_client(config)
    if notion is None or now is None:
        return False

    target = _resolve_notion_write_target(notion, config.notion_database_id)
    if target is None:
        return False

    missing = _missing_legacy_notion_properties(target.schema)
    if missing:
        log.error(f"Notion schema missing required properties: {', '.join(missing)}")
        return False

    notion_page_exists = _legacy_page_exists_today(notion, target, batch.topic, now)
    if notion_page_exists is None:
        return False
    if notion_page_exists:
        log.info(f"Notion duplicate skipped: '{batch.topic}' already exists today")
        return True

    payload = _build_legacy_page_payload(batch, trend, now)
    if payload is None:
        return False
    properties, body_blocks = payload
    return _create_legacy_notion_page(notion, target, properties, body_blocks, batch.topic)
