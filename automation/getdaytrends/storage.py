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

try:
    from .config import AppConfig
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from config import AppConfig
    from models import ScoredTrend, TweetBatch

# ???諛⑹떇蹂??꾪룷??try:
    from notion_client import Client as NotionClient
    from notion_client.errors import APIResponseError

    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
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
                delay = float(retry_after)
            else:
                delay = base_delay * (2**attempt)

            log.warning(
                f"Notion API ?먮윭 (HTTP {status}), " f"{delay:.1f}珥????ъ떆??({attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)

    # ?대줎?곸쑝濡??꾨떖 遺덇?, ?덉쟾?μ튂
    if last_exception:
        raise last_exception


try:
    import gspread
    from google.oauth2.service_account import Credentials

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


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

        asyncio.run(_runner())
    except Exception as exc:
        log.debug(f"Content Hub link persistence failed: {exc}")


def save_to_notion(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Notion DB????? ?띿꽦 + 由ъ튂 蹂몃Ц + ?대?吏."""
    if not NOTION_AVAILABLE:
        log.error("notion-client ?⑦궎吏媛 ?ㅼ튂?섏? ?딆븯?듬땲?? pip install notion-client")
        return False

    notion = NotionClient(auth=config.notion_token)
    now = datetime.now()

    # 硫깅벑??泥댄겕: ?ㅻ뒛 ?좎쭨???숈씪 ?ㅼ썙?쒓? ?대? ??λ맂 寃쎌슦 ?ㅽ궢
    today_str = now.strftime("%Y-%m-%d")
    if _notion_page_exists(notion, config.notion_database_id, batch.topic, today_str):
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
    body_blocks = _build_notion_body(batch, trend, image_url)

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

    properties = _content_hub_properties(
        schema,
        title=title,
        status=status,
        category=category,
        platform_label=platform_label,
        score=float(workflow_meta.get("qa_score", batch.viral_score or trend.viral_potential)),
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
                                f"Category: {category} | Score: {workflow_meta.get('qa_score', batch.viral_score or trend.viral_potential)}\n"
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

        row = [
            now,
            trend.rank,
            batch.topic,
            tweet_map.get("?? ??", ""),
            tweet_map.get("??? ???", ""),
            tweet_map.get("?? ???", ""),
            tweet_map.get("??? ???", ""),
            tweet_map.get("??/???", ""),
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
    except (ValueError, RuntimeError) as e:
        log.error(f"Google Sheets sync failed: {type(e).__name__}: {e}")
        return False

