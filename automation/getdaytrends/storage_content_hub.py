"""
getdaytrends — Content Hub Storage
Notion Content Hub V2.0 review-queue upsert.
storage.py에서 분리됨.
"""

from datetime import datetime
from typing import Any

from loguru import logger as log

try:
    from .config import AppConfig
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from config import AppConfig
    from models import ScoredTrend, TweetBatch

try:
    from .notion_builder import _build_notion_body
except ImportError:
    from notion_builder import _build_notion_body

from .storage_notion import (
    NOTION_AVAILABLE,
    NotionClient,
    _is_notion_provider_error,
    _persist_content_hub_link,
    _retry_notion_call,
)


# ══════════════════════════════════════════════════════
#  Helper Functions
# ══════════════════════════════════════════════════════


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


# ══════════════════════════════════════════════════════
#  Main: save_to_content_hub
# ══════════════════════════════════════════════════════


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
