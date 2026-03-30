"""Notion auto-publisher — push content pipeline results to a Notion database.

Supports the full 7-property schema for the content automation pipeline:
  - 제목 (Title)         → Article title
  - 프로젝트 (Select)     → Project classification
  - 작성일 (Date)         → Auto-generated date
  - 상태 (Status/Select)  → 초안 / 검토중 / 발행됨
  - 태그 (Multi-select)   → Topic tags
  - AI 모델 (Select)      → LLM model used
  - 원본 자료 (URL)       → Google Drive link
  - 첨부 파일 (Files)     → Infographic/slide file attachments

Extracted from ``getdaytrends/notebooklm_bridge.py::publish_to_notion``.
"""

from __future__ import annotations

from datetime import datetime

import httpx
from loguru import logger as log

from ..config import get_config

# ──────────────────────────────────────────────────
#  Block Builders
# ──────────────────────────────────────────────────


def _notion_block(block_type: str, content: str, **extra) -> dict:
    """Build a Notion block dict."""
    if block_type == "divider":
        return {"object": "block", "type": "divider", "divider": {}}
    inner = {"rich_text": [{"text": {"content": content}}]}
    inner.update(extra)
    return {"object": "block", "type": block_type, block_type: inner}


def _build_notion_children(
    article_body: str,
    *,
    summary: str = "",
    tweet: str = "",
    source_url: str = "",
    notebook_id: str = "",
    infographic_id: str = "",
    infographic_url: str = "",
    file_attachment_url: str = "",
) -> list[dict]:
    """Build Notion page children blocks from article content."""
    children: list[dict] = []

    # Article body → Notion blocks (Markdown line parsing)
    if article_body:
        for line in article_body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# "):
                children.append(_notion_block("heading_1", stripped[2:]))
            elif stripped.startswith("## "):
                children.append(_notion_block("heading_2", stripped[3:]))
            elif stripped.startswith("### "):
                children.append(_notion_block("heading_3", stripped[4:]))
            elif stripped.startswith("- ") or stripped.startswith("• "):
                children.append(_notion_block("bulleted_list_item", stripped[2:]))
            elif stripped.startswith("> "):
                children.append(_notion_block("quote", stripped[2:]))
            else:
                children.append(_notion_block("paragraph", stripped))

    children.append(_notion_block("divider", ""))

    # Summary section
    if summary:
        children.append(_notion_block("heading_2", "🧠 AI 인사이트"))
        children.append(_notion_block("paragraph", summary[:2000]))
        children.append(_notion_block("divider", ""))

    # Tweet draft section
    if tweet:
        children.append(_notion_block("heading_2", "🐦 트윗 초안"))
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "🐦"},
                    "rich_text": [{"text": {"content": tweet}}],
                },
            }
        )
        children.append(_notion_block("divider", ""))

    # Infographic image embed (external URL)
    if infographic_url and infographic_url.startswith("http"):
        children.append(_notion_block("heading_2", "📊 인포그래픽"))
        children.append(
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": infographic_url},
                    "caption": [{"text": {"content": "NotebookLM 자동 생성 인포그래픽"}}],
                },
            }
        )
        children.append(_notion_block("divider", ""))

    # Resources section
    resources: list[dict] = []
    if source_url:
        resources.append(_notion_block("bulleted_list_item", f"📎 원본 자료: {source_url}"))
    if notebook_id:
        nb_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
        resources.append(_notion_block("bulleted_list_item", f"📓 NotebookLM: {nb_url}"))
    if infographic_id:
        resources.append(_notion_block("bulleted_list_item", f"🎨 인포그래픽 ID: {infographic_id}"))

    if resources:
        children.append(_notion_block("heading_2", "🔗 리소스"))
        children.extend(resources)

    # File attachment (embed block for Drive files)
    if file_attachment_url:
        children.append(_notion_block("heading_2", "📎 첨부 파일"))
        children.append(
            {
                "object": "block",
                "type": "bookmark",
                "bookmark": {
                    "url": file_attachment_url,
                    "caption": [{"text": {"content": "원본 인포그래픽/슬라이드 파일"}}],
                },
            }
        )

    return children


# ──────────────────────────────────────────────────
#  Property Builders
# ──────────────────────────────────────────────────


def _build_properties(
    db_props: dict,
    *,
    title: str,
    project: str = "",
    status: str = "초안",
    tags: list[str] | None = None,
    ai_model: str = "",
    source_url: str = "",
    category: str = "",
) -> dict:
    """Build Notion page properties dynamically based on DB schema.

    Automatically detects the title field name and only sets properties
    that actually exist in the database schema.
    """
    properties: dict = {}

    # Find title field
    title_field = "Name"
    for prop_name, prop_info in db_props.items():
        if isinstance(prop_info, dict) and prop_info.get("type") == "title":
            title_field = prop_name
            break

    properties[title_field] = {"title": [{"text": {"content": title}}]}

    # 프로젝트 (Select)
    _set_select(properties, db_props, "프로젝트", project)
    _set_select(properties, db_props, "Project", project)

    # 상태 (Status or Select)
    _set_status_or_select(properties, db_props, status)

    # 태그 (Multi-select)
    if tags:
        _set_multi_select(properties, db_props, "태그", tags)
        _set_multi_select(properties, db_props, "Tags", tags)

    # AI 모델 (Select)
    _set_select(properties, db_props, "AI 모델", ai_model)
    _set_select(properties, db_props, "AI Model", ai_model)

    # 원본 자료 (URL)
    _set_url(properties, db_props, "원본 자료", source_url)
    _set_url(properties, db_props, "Source URL", source_url)

    # 카테고리 (Select) — legacy compatibility
    _set_select(properties, db_props, "Category", category)
    _set_select(properties, db_props, "카테고리", category)

    # 작성일 (Date) — auto-set to now
    _set_date(properties, db_props, "작성일")
    _set_date(properties, db_props, "Created Date")

    return properties


def _set_select(properties: dict, db_props: dict, name: str, value: str) -> None:
    """Set a select property if it exists in DB schema and value is non-empty."""
    if name in db_props and value and name not in properties:
        properties[name] = {"select": {"name": value}}


def _set_multi_select(properties: dict, db_props: dict, name: str, values: list[str]) -> None:
    """Set a multi-select property if it exists in DB schema."""
    if name in db_props and values and name not in properties:
        properties[name] = {"multi_select": [{"name": v} for v in values]}


def _set_url(properties: dict, db_props: dict, name: str, url: str) -> None:
    """Set a URL property if it exists."""
    if name in db_props and url and name not in properties:
        properties[name] = {"url": url}


def _set_status_or_select(properties: dict, db_props: dict, status: str) -> None:
    """Set status using Status type or fallback to Select."""
    for name in ("상태", "Status"):
        if name in db_props and name not in properties:
            prop_type = db_props[name].get("type", "select")
            if prop_type == "status":
                properties[name] = {"status": {"name": status}}
            else:
                properties[name] = {"select": {"name": status}}
            return


def _set_date(properties: dict, db_props: dict, name: str) -> None:
    """Set a date property to now if it exists."""
    if name in db_props and name not in properties:
        properties[name] = {"date": {"start": datetime.now().isoformat()}}


# ──────────────────────────────────────────────────
#  Main Publisher — Extended
# ──────────────────────────────────────────────────


async def publish_to_notion(
    factory_result: dict,
    notion_api_key: str | None = None,
    database_id: str | None = None,
) -> dict:
    """Publish content factory results to a Notion database.

    Supports both legacy (simple) and extended (7-property) schemas.

    Returns:
        ``{"notion_page_id": str, "notion_url": str}``
    """
    cfg = get_config()
    notion_api_key = notion_api_key or cfg.notion_api_key
    database_id = database_id or cfg.notion_database_id

    if not notion_api_key or not database_id:
        raise ValueError("Notion API key and database ID are required")

    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Discover DB schema
    async with httpx.AsyncClient() as http:
        db_resp = await http.get(
            f"https://api.notion.com/v1/databases/{database_id}",
            headers=headers,
            timeout=15,
        )
        db_resp.raise_for_status()
        db_schema = db_resp.json()

    db_props = db_schema.get("properties", {})

    # Extract fields from factory_result
    keyword = factory_result.get("keyword", "Analysis")
    title = factory_result.get("title", f"📊 {keyword}")
    article_body = factory_result.get("article_body", "")
    summary = factory_result.get("summary", "")[:2000]
    tweet = factory_result.get("tweet_draft", "")
    notebook_id = factory_result.get("notebook_id", "")
    infographic_id = factory_result.get("infographic_id", "")
    infographic_url = factory_result.get("infographic_url", "")
    source_url = factory_result.get("source_url", "")
    project = factory_result.get("project", "")
    status = factory_result.get("status", "초안")
    tags = factory_result.get("tags", [])
    ai_model = factory_result.get("ai_model", "")
    file_attachment_url = factory_result.get("file_attachment_url", "")
    category = factory_result.get("category", "기타")

    # Build properties
    properties = _build_properties(
        db_props,
        title=title,
        project=project,
        status=status,
        tags=tags,
        ai_model=ai_model,
        source_url=source_url,
        category=category,
    )

    # Build page children blocks
    children = _build_notion_children(
        article_body,
        summary=summary,
        tweet=tweet,
        source_url=source_url,
        notebook_id=notebook_id,
        infographic_id=infographic_id,
        infographic_url=infographic_url,
        file_attachment_url=file_attachment_url,
    )

    # Notion API limits children to 100 blocks per request
    page_data = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children[:100],
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=page_data,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    page_id = data["id"]
    notion_url = data.get("url", f"https://notion.so/{page_id.replace('-', '')}")
    log.info("[Notion] page created: %s", notion_url)

    # Append remaining blocks if > 100
    if len(children) > 100:
        remaining = children[100:]
        async with httpx.AsyncClient() as http:
            for chunk_start in range(0, len(remaining), 100):
                chunk = remaining[chunk_start : chunk_start + 100]
                await http.patch(
                    f"https://api.notion.com/v1/blocks/{page_id}/children",
                    headers=headers,
                    json={"children": chunk},
                    timeout=30,
                )
        log.info("[Notion] appended %d additional blocks", len(remaining))

    return {"notion_page_id": page_id, "notion_url": notion_url}
