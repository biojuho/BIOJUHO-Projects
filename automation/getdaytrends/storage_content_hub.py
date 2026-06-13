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

try:
    from .storage_notion import (
        NOTION_AVAILABLE,
        NotionClient,
        _is_notion_provider_error,
        _persist_content_hub_link,
        _query_notion_target,
        _resolve_notion_write_target,
        _retry_notion_call,
    )
except ImportError:
    from storage_notion import (
        NOTION_AVAILABLE,
        NotionClient,
        _persist_content_hub_link,
        _query_notion_target,
        _resolve_notion_write_target,
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
        target = _resolve_notion_write_target(notion, database_id)
        return target.schema if target is not None else {}
    except Exception as exc:
        log.debug(f"Content Hub schema lookup failed: {exc}")
        return {}


def _query_content_hub_by_draft_id(notion: Any, database_id: str, draft_id: str) -> str:
    if not draft_id:
        return ""
    try:
        target = _resolve_notion_write_target(notion, database_id)
        if target is None:
            return ""
        results = _query_notion_target(
            notion,
            target,
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


def _set_schema_prop(props: dict[str, Any], schema: dict[str, Any], name: str, value: dict, *, include: bool = True) -> None:
    if include and name in schema:
        props[name] = value


def _base_content_hub_properties(
    schema: dict[str, Any],
    *,
    title: str,
    status: str,
    category: str,
    platform_label: str,
    score: float,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    base_fields = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Status": {"select": {"name": status}},
        "Category": {"select": {"name": category}},
        "Date": {"date": {"start": datetime.now().date().isoformat()}},
        "Score": {"number": score},
        "Platform": {"multi_select": [{"name": platform_label}]},
    }
    for name, value in base_fields.items():
        _set_schema_prop(props, schema, name, value)
    return props


def _draft_meta_content_hub_properties(schema: dict[str, Any], draft_meta: dict) -> dict[str, Any]:
    props: dict[str, Any] = {}
    text_fields = {
        "Trend ID": draft_meta.get("trend_id"),
        "Draft ID": draft_meta.get("draft_id"),
        "Prompt Version": draft_meta.get("prompt_version"),
        "Blocking Reasons": ", ".join(draft_meta.get("blocking_reasons", []) or []),
    }
    for name, value in text_fields.items():
        _set_schema_prop(props, schema, name, _rich_text_prop(str(value)), include=bool(value) or name == "Blocking Reasons")

    if draft_meta.get("qa_score") is not None:
        _set_schema_prop(props, schema, "QA Score", {"number": float(draft_meta.get("qa_score", 0.0))})
    return props


def _published_content_hub_properties(
    schema: dict[str, Any],
    *,
    published_url: str,
    published_at: str,
    receipt_id: str,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    _set_schema_prop(props, schema, "Published URL", {"url": published_url}, include=bool(published_url))
    _set_schema_prop(props, schema, "Published At", {"date": {"start": published_at}}, include=bool(published_at))
    _set_schema_prop(props, schema, "Receipt ID", _rich_text_prop(receipt_id), include=bool(receipt_id))
    _set_schema_prop(props, schema, "URL", {"url": published_url}, include=bool(published_url))
    return props


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
    props = _base_content_hub_properties(
        schema,
        title=title,
        status=status,
        category=category,
        platform_label=platform_label,
        score=score,
    )
    props.update(_draft_meta_content_hub_properties(schema, draft_meta))
    props.update(
        _published_content_hub_properties(
            schema,
            published_url=published_url,
            published_at=published_at,
            receipt_id=receipt_id,
        )
    )
    return props


def _content_hub_default_priority(score: float) -> str:
    if score >= 85:
        return "High"
    if score >= 70:
        return "Medium"
    return "Low"


def _content_hub_platform_label(platform: str) -> str:
    return {"x": "X", "threads": "Threads", "naver_blog": "NaverBlog"}.get(platform, platform)


def _content_hub_review_context(
    batch: TweetBatch,
    trend: ScoredTrend,
    platform: str,
    workflow_meta: dict,
) -> dict[str, Any]:
    platform_label = _content_hub_platform_label(platform)
    review_score = float(workflow_meta.get("qa_score", batch.viral_score or trend.viral_potential))
    return {
        "platform_label": platform_label,
        "category": getattr(trend, "category", "湲고?") or "湲고?",
        "status": "Ready",
        "title": f"[{platform_label}] {batch.topic} | {datetime.now().strftime('%m/%d %H:%M')}",
        "review_score": review_score,
    }


def _content_hub_summary_block(context: dict[str, Any], workflow_meta: dict) -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "?뱷"},
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": (
                            f"Platform: {context['platform_label']} | Status: {context['status']}\n"
                            f"Category: {context['category']} | Score: {context['review_score']}\n"
                            f"Draft ID: {workflow_meta.get('draft_id', '')}\n"
                            f"Prompt Version: {workflow_meta.get('prompt_version', '')}"
                        )
                    },
                }
            ],
            "color": "blue_background",
        },
    }


def _plain_code_block(content: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "language": "plain text",
            "rich_text": [{"type": "text", "text": {"content": content[:1900]}}],
        },
    }


def _paragraph_block(content: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": content[:1900]}}],
        },
    }


def _content_hub_body_blocks(batch: TweetBatch, trend: ScoredTrend, platform: str) -> list[dict]:
    if platform == "x":
        return _build_notion_body(batch, trend)
    if platform == "threads":
        return [_plain_code_block(post.content) for post in batch.threads_posts]
    if platform == "naver_blog":
        return [_paragraph_block(post.content) for post in batch.blog_posts]
    return []


def _seed_content_hub_create_defaults(properties: dict[str, Any], schema: dict[str, Any], review_score: float) -> None:
    defaults = {
        "Feedback State": {"select": {"name": "Need Review"}},
        "Next Action": {"select": {"name": "Review Copy"}},
        "Priority": {"select": {"name": _content_hub_default_priority(review_score)}},
    }
    for name, value in defaults.items():
        _set_schema_prop(properties, schema, name, value)


def _existing_content_hub_page_id(notion: Any, schema: dict[str, Any], hub_db_id: str, workflow_meta: dict) -> str:
    if "Draft ID" not in schema or not workflow_meta.get("draft_id"):
        return ""
    return _query_content_hub_by_draft_id(notion, hub_db_id, workflow_meta.get("draft_id", ""))


def _upsert_content_hub_page(
    notion: Any,
    *,
    hub_db_id: str,
    existing_page_id: str,
    properties: dict[str, Any],
    blocks: list[dict],
) -> str:
    if existing_page_id:
        _retry_notion_call(notion.pages.update, page_id=existing_page_id, properties=properties)
        return existing_page_id

    target = _resolve_notion_write_target(notion, hub_db_id)
    if target is None:
        return ""

    page = _retry_notion_call(
        notion.pages.create,
        parent=target.parent,
        properties=properties,
        children=blocks,
    )
    return page.get("id", "") if isinstance(page, dict) else ""


def _content_hub_database_id(config: AppConfig) -> str | None:
    hub_db_id = getattr(config, "content_hub_database_id", "")
    if not hub_db_id:
        return None
    if not NOTION_AVAILABLE:
        log.error("notion-client package is required for Content Hub writes")
        return None
    return hub_db_id


def _should_skip_content_hub(batch: TweetBatch, platform: str, workflow_meta: dict) -> bool:
    if (getattr(batch, "metadata", {}) or {}).get("workflow_v2") and not workflow_meta:
        log.info(f"Content Hub skip [{platform}] '{batch.topic}' - no ready V2 draft")
        return True
    return False


def _prepare_content_hub_payload(
    notion: Any,
    *,
    hub_db_id: str,
    batch: TweetBatch,
    trend: ScoredTrend,
    platform: str,
    workflow_meta: dict,
) -> tuple[dict[str, Any], dict[str, Any], list[dict], str]:
    schema = _get_hub_schema(notion, hub_db_id)
    context = _content_hub_review_context(batch, trend, platform, workflow_meta)
    properties = _content_hub_properties(
        schema,
        title=context["title"],
        status=context["status"],
        category=context["category"],
        platform_label=context["platform_label"],
        score=context["review_score"],
        draft_meta=workflow_meta,
    )
    blocks = [_content_hub_summary_block(context, workflow_meta), *_content_hub_body_blocks(batch, trend, platform)][:100]
    existing_page_id = _existing_content_hub_page_id(notion, schema, hub_db_id, workflow_meta)
    if not existing_page_id:
        _seed_content_hub_create_defaults(properties, schema, context["review_score"])
    return context, properties, blocks, existing_page_id


def _log_content_hub_error(exc: Exception, context: dict[str, Any]) -> None:
    platform_label = context.get("platform_label", "unknown")
    if isinstance(exc, (ConnectionError, TimeoutError)):
        log.error(f"Content Hub network error [{platform_label}]: {type(exc).__name__}: {exc}")
    else:
        log.error(f"Content Hub upsert failed [{platform_label}]: {type(exc).__name__}: {exc}")


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
    hub_db_id = _content_hub_database_id(config)
    if not hub_db_id:
        return False

    workflow_meta = _content_hub_workflow_meta(batch, platform)
    if _should_skip_content_hub(batch, platform, workflow_meta):
        return True

    notion = NotionClient(auth=config.notion_token)
    context: dict[str, Any] = {}
    try:
        context, properties, blocks, existing_page_id = _prepare_content_hub_payload(
            notion,
            hub_db_id=hub_db_id,
            batch=batch,
            trend=trend,
            platform=platform,
            workflow_meta=workflow_meta,
        )
        page_id = _upsert_content_hub_page(
            notion,
            hub_db_id=hub_db_id,
            existing_page_id=existing_page_id,
            properties=properties,
            blocks=blocks,
        )
        if page_id and workflow_meta.get("draft_id"):
            _persist_content_hub_link(config, workflow_meta["draft_id"], page_id, context["status"])

        log.info(f"Content Hub upsert complete [{context['platform_label']}] '{batch.topic}'")
        return True
    except Exception as exc:
        _log_content_hub_error(exc, context)
        return False
