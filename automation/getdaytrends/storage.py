"""
getdaytrends v2.4 - Storage Module
Notion + Google Sheets + SQLite ????쇱슦??
Notion API ?ъ떆??濡쒖쭅 (吏??諛깆삤?? ?ы븿.
"""

import asyncio
import json
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

# Notion API ?ъ떆?????HTTP ?곹깭 肄붾뱶
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_MAX_RETRIES = 4
_BASE_DELAY = 1.0  # 珥?(1s ??2s ??4s ??8s)


def _retry_notion_call(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
    **kwargs: Any,
) -> Any:
    """
    Notion API ?몄텧??吏??諛깆삤?꾨줈 ?ъ떆??

    429 (Rate Limit), 500, 502, 503 ?먮윭 諛쒖깮 ??理쒕? max_retries ???ъ떆??
    429??寃쎌슦 Retry-After ?ㅻ뜑媛 ?덉쑝硫??대떦 ?쒓컙留뚰겮 ?湲?
    洹????먮윭??利됱떆 raise.

    Args:
        fn: ?몄텧??Notion API ?⑥닔 (?? notion.pages.create)
        *args: ?꾩튂 ?몄옄
        max_retries: 理쒕? ?ъ떆???잛닔 (湲곕낯 4)
        base_delay: 湲곕낯 ?湲??쒓컙 (湲곕낯 1珥? 吏??利앷?)
        **kwargs: ?ㅼ썙???몄옄

    Returns:
        Notion API ?묐떟

    Raises:
        APIResponseError: ?ъ떆???잛닔 珥덇낵 ?먮뒗 ?ъ떆??遺덇??ν븳 ?먮윭
        Exception: Notion API ?몄쓽 ?덉쇅
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # notion-client 媛 ?녾굅??APIResponseError媛 ?꾨땶 寃쎌슦 利됱떆 raise
            if APIResponseError is None or not isinstance(e, APIResponseError):
                raise

            status = getattr(e, "status", None)
            if status not in _RETRYABLE_STATUS_CODES:
                raise  # ?ъ떆??遺덇??ν븳 ?먮윭 (400, 401, 404 ??

            last_exception = e

            if attempt >= max_retries:
                log.error(f"Notion API ?ъ떆???쒕룄 珥덇낵 (HTTP {status}): " f"{max_retries + 1}???쒕룄 ???ㅽ뙣")
                raise

            # 429??寃쎌슦 Retry-After ?ㅻ뜑 ?뺤씤
            retry_after = None
            if status == 429:
                # notion-client??APIResponseError?먮뒗 headers媛 ?놁쓣 ???덉쓬
                # body??retry_after媛 ?덉쓣 ???덉쓬
                body = getattr(e, "body", None)
                if isinstance(body, dict):
                    retry_after = body.get("retry_after")

            if retry_after and isinstance(retry_after, (int, float)):
                delay = min(float(retry_after), 60.0)  # H-06 fix: 최대 60초 캡
            else:
                delay = min(base_delay * (2**attempt), 60.0)

            log.warning(
                f"Notion API ?먮윭 (HTTP {status}), " f"{delay:.1f}珥????ъ떆??({attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)

    # ?대줎?곸쑝濡??꾨떖 遺덇?, ?덉쟾?μ튂
    if last_exception:
        raise last_exception


try:
    import gspread
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2.service_account import Credentials

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None  # type: ignore
    Credentials = None  # type: ignore
    GoogleAuthError = None  # type: ignore


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


def _is_notion_provider_error(exc: Exception) -> bool:
    return APIResponseError is not None and isinstance(exc, APIResponseError)


def _is_gspread_provider_error(exc: Exception) -> bool:
    candidates: list[type[BaseException]] = []
    if GSPREAD_AVAILABLE and gspread is not None:
        gspread_exceptions = getattr(gspread, "exceptions", None)
        if gspread_exceptions is not None:
            for name in ("APIError", "GSpreadException", "SpreadsheetNotFound", "WorksheetNotFound"):
                candidate = getattr(gspread_exceptions, name, None)
                if isinstance(candidate, type):
                    candidates.append(candidate)
    if isinstance(GoogleAuthError, type):
        candidates.append(GoogleAuthError)
    return any(isinstance(exc, candidate) for candidate in candidates)


def _content_hub_workflow_meta(batch: TweetBatch, platform: str) -> dict:
    workflow = (getattr(batch, "metadata", {}) or {}).get("workflow_v2", {}) or {}
    drafts = workflow.get("drafts", []) or []
    return next((item for item in drafts if item.get("platform") == platform and item.get("passed")), {})


def _get_hub_schema(notion: Any, database_id: str) -> dict[str, Any]:
    try:
        response = _retry_notion_call(notion.databases.retrieve, database_id=database_id)
        return response.get("properties", {}) if isinstance(response, dict) else {}
    except Exception as exc:
        log.debug(f"Content Hub schema lookup failed: {exc}")
        return {}


def _query_content_hub_by_draft_id(notion: Any, database_id: str, draft_id: str) -> str:
    if not draft_id:
        return ""
    try:
        results = _retry_notion_call(
            notion.databases.query,
            database_id=database_id,
            filter={"property": "Draft ID", "rich_text": {"equals": draft_id}},
            page_size=1,
        )
    except Exception as exc:
        log.debug(f"Content Hub draft query failed: {exc}")
        return ""

    rows = results.get("results", []) if isinstance(results, dict) else []
    if not rows:
        return ""
    return rows[0].get("id", "")


def _rich_text_prop(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:1900]}}]}


def _content_hub_properties(
    schema: dict[str, Any],
    *,
    title: str,
    status: str,
    category: str,
    platform_label: str,
    score: float,
    draft_meta: dict,
    published_url: str = "",
    published_at: str = "",
    receipt_id: str = "",
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if "Name" in schema:
        props["Name"] = {"title": [{"text": {"content": title}}]}
    if "Status" in schema:
        props["Status"] = {"select": {"name": status}}
    if "Category" in schema:
        props["Category"] = {"select": {"name": category}}
    if "Date" in schema:
        props["Date"] = {"date": {"start": datetime.now().date().isoformat()}}
    if "Score" in schema:
        props["Score"] = {"number": score}
    if "Platform" in schema:
        props["Platform"] = {"multi_select": [{"name": platform_label}]}
    if "Trend ID" in schema and draft_meta.get("trend_id"):
        props["Trend ID"] = _rich_text_prop(str(draft_meta["trend_id"]))
    if "Draft ID" in schema and draft_meta.get("draft_id"):
        props["Draft ID"] = _rich_text_prop(str(draft_meta["draft_id"]))
    if "Prompt Version" in schema and draft_meta.get("prompt_version"):
        props["Prompt Version"] = _rich_text_prop(str(draft_meta["prompt_version"]))
    if "QA Score" in schema and draft_meta.get("qa_score") is not None:
        props["QA Score"] = {"number": float(draft_meta.get("qa_score", 0.0))}
    if "Blocking Reasons" in schema:
        blockers = ", ".join(draft_meta.get("blocking_reasons", []) or [])
        props["Blocking Reasons"] = _rich_text_prop(blockers)
    if "Published URL" in schema and published_url:
        props["Published URL"] = {"url": published_url}
    if "Published At" in schema and published_at:
        props["Published At"] = {"date": {"start": published_at}}
    if "Receipt ID" in schema and receipt_id:
        props["Receipt ID"] = _rich_text_prop(receipt_id)
    if "URL" in schema and published_url:
        props["URL"] = {"url": published_url}
    return props


def _content_hub_default_priority(score: float) -> str:
    if score >= 85:
        return "High"
    if score >= 70:
        return "Medium"
    return "Low"


def _persist_content_hub_link(config: AppConfig, draft_id: str, page_id: str, review_status: str) -> None:
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
            # B-003 fix: Task 객체를 _bg_tasks에 보관하여 GC 수거 방지 + 예외 명시 로깅
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


def save_to_notion(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Notion DB????? ?띿꽦 + 由ъ튂 蹂몃Ц + ?대?吏."""
    if not NOTION_AVAILABLE:
        log.error("notion-client ?⑦궎吏媛 ?ㅼ튂?섏? ?딆븯?듬땲?? pip install notion-client")
        return False

    try:
        notion = NotionClient(auth=config.notion_token)
        now = datetime.now()
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Notion ??????쎈뱜??곌쾿 ??살첒: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Notion ??????쎈솭 (??됯맒??: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        if _is_notion_provider_error(e):
            log.error(f"Notion provider error: {type(e).__name__}: {e}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(e).__name__}: {e}")
        return False

    # 硫깅벑??泥댄겕: ?ㅻ뒛 ?좎쭨???숈씪 ?ㅼ썙?쒓? ?대? ??λ맂 寃쎌슦 ?ㅽ궢
    today_str = now.strftime("%Y-%m-%d")
    try:
        notion_page_exists = _notion_page_exists(notion, config.notion_database_id, batch.topic, today_str)
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Notion ???????덈콦??怨뚯씩 ???댁쾼: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Notion ???????덉넮 (????쭜??: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        if _is_notion_provider_error(e):
            log.error(f"Notion provider error: {type(e).__name__}: {e}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(e).__name__}: {e}")
        return False
    if notion_page_exists:
        log.info(f"Notion 以묐났 ?ㅽ궢: '{batch.topic}' (?ㅻ뒛 ?대? ??λ맖)")
        return True

    tweet_map = {t.tweet_type: t.content for t in batch.tweets}
    title = f"[Trend #{trend.rank}] {batch.topic} | {now.strftime('%Y-%m-%d %H:%M')}"
    image_url = ""
    properties = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Topic": {"rich_text": [{"text": {"content": batch.topic}}]},
        "Rank": {"number": trend.rank},
        "Created At": {"date": {"start": now.isoformat()}},
        "Empathy": {"rich_text": [{"text": {"content": tweet_map.get("공감 도입", "")}}]},
        "Curiosity": {"rich_text": [{"text": {"content": tweet_map.get("가벼운 궁금형", "")}}]},
        "Question": {"rich_text": [{"text": {"content": tweet_map.get("차별 질문형", "")}}]},
        "Quote": {"rich_text": [{"text": {"content": tweet_map.get("알려줌 명언형", "")}}]},
        "Reaction": {"rich_text": [{"text": {"content": tweet_map.get("양자/반응형", "")}}]},
        "Status": {"select": {"name": "Ready"}},
    }

    properties["Viral Score"] = {"number": trend.viral_potential}

    platforms = getattr(config, "target_platforms", ["x"])
    platform_labels = []
    if "x" in platforms:
        platform_labels.append("X")
    if "threads" in platforms and batch.threads_posts:
        platform_labels.append("Threads")
    if "naver_blog" in platforms and batch.blog_posts:
        platform_labels.append("NaverBlog")
    # properties???ｌ? ?딆쓬 ??DB ?ㅽ궎留덉뿉 ?띿꽦???놁쓣 ???덉쓬

    if batch.thread:
        thread_text = "\n---\n".join(batch.thread.tweets)
        # Notion? UTF-16 肄붾뱶 ?좊떅 湲곗? 2000???쒗븳 (?대え吏=2?좊떅)
        properties["Thread"] = {"rich_text": [{"text": {"content": thread_text[:1900]}}]}

    # 蹂몃Ц 釉붾줉 ?앹꽦
    try:
        body_blocks = _build_notion_body(batch, trend, image_url)
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Notion ??????쎈뱜??곌쾿 ??살첒: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Notion ??????쎈솭 (??됯맒??: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        if _is_notion_provider_error(e):
            log.error(f"Notion provider error: {type(e).__name__}: {e}")
        else:
            log.error(f"Notion sync failed unexpectedly: {type(e).__name__}: {e}")
        return False

    try:
        _retry_notion_call(
            notion.pages.create,
            parent={"database_id": config.notion_database_id},
            properties=properties,
            children=body_blocks,
        )
        log.info(f"Notion ????꾨즺: '{title}' (蹂몃Ц {len(body_blocks)}釉붾줉)")
        return True
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Notion ????ㅽ듃?뚰겕 ?ㅻ쪟: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Notion ????ㅽ뙣 (?덉긽??: {type(e).__name__}: {e}")
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


def save_to_content_hub(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
    platform: str = "x",
) -> bool:
    """Upsert one V2.0 review-queue page into the canonical Notion Content Hub."""
    hub_db_id = getattr(config, "content_hub_database_id", "")
    if not hub_db_id:
        return False
    if not NOTION_AVAILABLE:
        log.error("notion-client package is required for Content Hub writes")
        return False

    workflow_meta = _content_hub_workflow_meta(batch, platform)
    if (getattr(batch, "metadata", {}) or {}).get("workflow_v2") and not workflow_meta:
        log.info(f"Content Hub skip [{platform}] '{batch.topic}' - no ready V2 draft")
        return True

    notion = NotionClient(auth=config.notion_token)
    schema = _get_hub_schema(notion, hub_db_id)
    now = datetime.now()

    platform_emoji = {"x": "X", "threads": "T", "naver_blog": "B"}.get(platform, "Q")
    platform_label = {"x": "X", "threads": "Threads", "naver_blog": "NaverBlog"}.get(platform, platform)
    category = getattr(trend, "category", "기타") or "기타"
    status = "Ready"
    title = f"[{platform_label}] {batch.topic} | {now.strftime('%m/%d %H:%M')}"
    review_score = float(workflow_meta.get("qa_score", batch.viral_score or trend.viral_potential))

    properties = _content_hub_properties(
        schema,
        title=title,
        status=status,
        category=category,
        platform_label=platform_label,
        score=review_score,
        draft_meta=workflow_meta,
    )

    blocks: list[dict] = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📝"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": (
                                f"Platform: {platform_label} | Status: {status}\n"
                                f"Category: {category} | Score: {review_score}\n"
                                f"Draft ID: {workflow_meta.get('draft_id', '')}\n"
                                f"Prompt Version: {workflow_meta.get('prompt_version', '')}"
                            )
                        },
                    }
                ],
                "color": "blue_background",
            },
        }
    ]

    if platform == "x":
        blocks.extend(_build_notion_body(batch, trend))
    elif platform == "threads":
        for post in batch.threads_posts:
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"type": "text", "text": {"content": post.content[:1900]}}],
                    },
                }
            )
    elif platform == "naver_blog":
        for post in batch.blog_posts:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": post.content[:1900]}}],
                    },
                }
            )

    if len(blocks) > 100:
        blocks = blocks[:100]

    existing_page_id = ""
    if "Draft ID" in schema and workflow_meta.get("draft_id"):
        existing_page_id = _query_content_hub_by_draft_id(notion, hub_db_id, workflow_meta.get("draft_id", ""))
    if not existing_page_id:
        if "Feedback State" in schema:
            properties["Feedback State"] = {"select": {"name": "Need Review"}}
        if "Next Action" in schema:
            properties["Next Action"] = {"select": {"name": "Review Copy"}}
        if "Priority" in schema:
            properties["Priority"] = {"select": {"name": _content_hub_default_priority(review_score)}}

    try:
        if existing_page_id:
            _retry_notion_call(notion.pages.update, page_id=existing_page_id, properties=properties)
            page_id = existing_page_id
        else:
            page = _retry_notion_call(
                notion.pages.create,
                parent={"database_id": hub_db_id},
                properties=properties,
                children=blocks,
            )
            page_id = page.get("id", "") if isinstance(page, dict) else ""

        if page_id and workflow_meta.get("draft_id"):
            _persist_content_hub_link(config, workflow_meta["draft_id"], page_id, status)

        log.info(f"Content Hub upsert complete [{platform_label}] '{batch.topic}'")
        return True
    except (ConnectionError, TimeoutError) as exc:
        log.error(f"Content Hub network error [{platform_label}]: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        log.error(f"Content Hub upsert failed [{platform_label}]: {type(exc).__name__}: {exc}")
        return False


def save_to_google_sheets(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Append one batch to Google Sheets using a stable V2-compatible schema."""
    if not GSPREAD_AVAILABLE:
        log.error("gspread package is not installed. Run: pip install gspread google-auth")
        return False

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(config.google_service_json, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(config.google_sheet_id).sheet1

        if sheet.row_count == 0 or not sheet.cell(1, 1).value:
            headers = [
                "Created",
                "Rank",
                "Topic",
                "Empathy",
                "Curiosity",
                "Question",
                "Quote",
                "Reaction",
                "Status",
                "Viral Score",
                "Thread",
            ]
            sheet.append_row(headers, value_input_option="USER_ENTERED")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tweet_map = {t.tweet_type: t.content for t in batch.tweets}
        thread_text = "\n---\n".join(batch.thread.tweets) if batch.thread else ""

        # B-010 fix: tweet_type 키를 영어로 통일 (Mojibake 컬럼 매핑 오류 방지)
        # tweet_type 값은 models.py의 영문 상수와 일치해야 함
        row = [
            now,
            trend.rank,
            batch.topic,
            tweet_map.get("empathy", tweet_map.get("공감형", "")),
            tweet_map.get("curiosity", tweet_map.get("호기심형", "")),
            tweet_map.get("question", tweet_map.get("질문형", "")),
            tweet_map.get("quote", tweet_map.get("인용형", "")),
            tweet_map.get("reaction", tweet_map.get("반응/토론형", "")),
            "Ready",
            trend.viral_potential,
            thread_text[:2000],
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")

        log.info(f"Google Sheets sync complete: '{batch.topic}'")
        return True

    except FileNotFoundError:
        log.error(f"Service account JSON not found: {config.google_service_json}")
        return False
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Google Sheets network error: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        if _is_gspread_provider_error(e):
            # B-019 fix: gspread APIError (429 Rate Limit, SpreadsheetNotFound 등) 명시 처리
            log.error(f"Google Sheets API error (gspread): {type(e).__name__}: {e}")
        else:
            log.error(f"Google Sheets sync failed: {type(e).__name__}: {e}")
        return False

