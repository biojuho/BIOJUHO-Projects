"""Utilities for publishing generated content to Notion."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger as log

if TYPE_CHECKING:
    from config import CIEConfig
    from storage.models import ContentBatch, GeneratedContent, PublishResult


async def publish_to_notion(
    content: GeneratedContent,
    config: CIEConfig,
) -> PublishResult:
    """Publish a single generated content item to the Notion content hub."""
    from storage.models import PublishResult

    if not config.can_publish_notion:
        return PublishResult(
            platform=content.platform,
            success=False,
            target="notion",
            error="Notion publishing is disabled (set CIE_NOTION_PUBLISH=true)",
        )

    try:
        import asyncio as _asyncio

        import httpx

        headers = {
            "Authorization": f"Bearer {config.notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        body_text = content.body[:2000] if content.body else "(No body)"
        body_blocks = _split_to_blocks(body_text)

        tag_items = [{"name": kw[:100]} for kw in content.trend_keywords_used[:5]]
        if content.hashtags:
            tag_items.extend({"name": hashtag[:100]} for hashtag in content.hashtags[:5])

        default_title = content.trend_keywords_used[0] if content.trend_keywords_used else "CIE Content"
        payload = {
            "parent": {"database_id": config.notion_database_id},
            "properties": {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": content.title or f"[{content.platform.upper()}] {default_title}",
                            }
                        }
                    ]
                },
                "Status": {"select": {"name": "Draft"}},
                "Platform": {"select": {"name": content.platform.upper()}},
                "Score": {"number": content.qa_report.total_score if content.qa_report else 0},
                "Tags": {"multi_select": tag_items},
            },
            "children": body_blocks,
        }

        resp: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _attempt in range(3):
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code != 429:
                    break
                retry_after = min(int(resp.headers.get("retry-after", "2")), 30)
                log.warning("Notion rate limited; retrying in {}s", retry_after)
                await _asyncio.sleep(retry_after)

        if resp is not None and resp.status_code == 200:
            page_id = resp.json().get("id", "")
            content.notion_page_id = page_id
            content.published_at = datetime.now()
            content.publish_target = "notion"

            log.info(
                "Notion publish succeeded: {}/{} -> {}",
                content.platform,
                content.content_type,
                page_id,
            )
            return PublishResult(
                platform=content.platform,
                success=True,
                target="notion",
                page_id=page_id,
            )

        if resp is None:
            error = "No response received from Notion API"
        else:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"

        log.warning("Notion publish failed: {}", error)
        content.publish_error = error
        return PublishResult(
            platform=content.platform,
            success=False,
            target="notion",
            error=error,
        )

    except Exception as exc:
        error = str(exc)
        log.error("Notion publish error: {}", error)
        content.publish_error = error
        return PublishResult(
            platform=content.platform,
            success=False,
            target="notion",
            error=error,
        )


async def publish_batch_to_notion(
    batch: ContentBatch,
    config: CIEConfig,
) -> list[PublishResult]:
    """Publish all QA-passed content items in a batch to Notion."""
    results: list[PublishResult] = []
    for content in batch.contents:
        if content.qa_passed:
            result = await publish_to_notion(content, config)
            results.append(result)
    return results


def _split_to_blocks(text: str, max_len: int = 2000) -> list[dict[str, Any]]:
    """Convert plain text into simple Notion paragraph blocks."""
    blocks: list[dict[str, Any]] = []
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        while len(para) > max_len:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": para[:max_len]}}]
                    },
                }
            )
            para = para[max_len:]

        if para:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": para}}]
                    },
                }
            )

    return blocks or [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(Empty body)"}}]},
        }
    ]
