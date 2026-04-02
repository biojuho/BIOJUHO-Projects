from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any

import httpx
from notion_client import AsyncClient

from antigravity_mcp.config import AppSettings, get_settings
from antigravity_mcp.domain.markdown_blocks import block_to_text, markdown_to_blocks
from antigravity_mcp.domain.models import PageSummary
from shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0

# Shared circuit breaker for all Notion API calls within this process.
_notion_breaker = CircuitBreaker("notion", failure_threshold=5, cooldown_sec=60)


def _should_retry(exc: Exception) -> bool:
    """Return True for 429 rate-limit and 5xx server errors."""
    if hasattr(exc, "status"):
        return exc.status == 429 or exc.status >= 500
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def retry_notion_call(func):
    """Decorator that retries an async Notion API call with exponential backoff and circuit breaker."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not _notion_breaker.allow_request():
            raise NotionAdapterError(
                "circuit_open",
                "Notion circuit breaker is OPEN — calls are temporarily blocked after repeated failures.",
                retryable=True,
            )
        backoff = _INITIAL_BACKOFF
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await func(*args, **kwargs)
                _notion_breaker.record_success()
                return result
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES and _should_retry(exc):
                    wait = backoff * (2**attempt)
                    logger.warning(
                        "Notion API retry attempt %d/%d after %.1fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                _notion_breaker.record_failure()
                raise
        _notion_breaker.record_failure()
        raise last_exc  # pragma: no cover

    return wrapper


class NotionAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class NotionAdapter:
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        api_key: str | None = None,
        client: AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.notion_api_key
        self.client = client or (AsyncClient(auth=self.api_key) if self.api_key else None)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    @retry_notion_call
    async def search(
        self,
        *,
        query: str,
        object_type: str = "page",
        limit: int = 10,
        cursor: str = "",
    ) -> tuple[list[PageSummary], str]:
        self._require_client()
        kwargs: dict[str, Any] = {"query": query, "page_size": limit}
        if object_type:
            kwargs["filter"] = {"property": "object", "value": object_type}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = await self.client.search(**kwargs)
        results = [self._to_page_summary(result) for result in response.get("results", [])]
        return results, response.get("next_cursor", "") or ""

    @retry_notion_call
    async def get_page(self, *, page_id: str, include_blocks: bool, max_depth: int = 1) -> dict[str, Any]:
        self._require_client()
        page = await self.client.pages.retrieve(page_id=page_id)
        payload = {
            "page": self._to_page_summary(page).to_dict(),
            "properties": page.get("properties", {}),
        }
        if include_blocks:
            blocks = await self._collect_block_text(page_id, max_depth=max_depth)
            payload["blocks"] = blocks
            payload["markdown"] = "\n\n".join(blocks)
        return payload

    @retry_notion_call
    async def create_page(
        self,
        *,
        parent_page_id: str,
        title: str,
        markdown: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_client()
        page = await self.client.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {"title": [{"type": "text", "text": {"content": title}}]},
                **(properties or {}),
            },
            children=markdown_to_blocks(markdown),
        )
        return {
            "id": page.get("id", ""),
            "url": page.get("url", ""),
            "title": title,
        }

    @retry_notion_call
    async def create_record(
        self,
        *,
        database_id: str,
        properties: dict[str, Any],
        markdown: str,
    ) -> dict[str, Any]:
        self._require_client()
        page = await self.client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=markdown_to_blocks(markdown),
        )
        return {
            "id": page.get("id", ""),
            "url": page.get("url", ""),
        }

    @retry_notion_call
    async def append_markdown(self, *, page_id: str, markdown: str) -> dict[str, Any]:
        self._require_client()
        blocks = markdown_to_blocks(markdown)
        if not blocks:
            return {"appended_blocks": 0}
        await self.client.blocks.children.append(block_id=page_id, children=blocks)
        return {"appended_blocks": len(blocks)}

    @retry_notion_call
    async def query_database(
        self,
        *,
        database_id: str,
        filter_payload: dict[str, Any] | None = None,
        limit: int = 20,
        cursor: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        if not self.api_key:
            raise NotionAdapterError("notion_not_configured", "NOTION_API_KEY is missing.")
        payload: dict[str, Any] = {"page_size": limit}
        if filter_payload:
            payload["filter"] = filter_payload
        if cursor:
            payload["start_cursor"] = cursor
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.settings.notion_api_version,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.pipeline_http_timeout_sec) as client:
            response = await client.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            raise NotionAdapterError(
                "notion_query_failed",
                f"Notion database query failed with status {response.status_code}: {response.text}",
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        body = response.json()
        return body.get("results", []), body.get("next_cursor", "") or ""

    @retry_notion_call
    async def query_data_source(
        self,
        *,
        data_source_id: str,
        filter_payload: dict[str, Any] | None = None,
        limit: int = 20,
        cursor: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        """Backward-compatible alias.

        The Notion workspace in this project expects database query endpoints.
        Keep the legacy method name so older call sites do not break, but route
        the request through the standard database query path.
        """
        return await self.query_database(
            database_id=data_source_id,
            filter_payload=filter_payload,
            limit=limit,
            cursor=cursor,
        )

    async def list_child_blocks(self, page_id: str) -> list[dict[str, Any]]:
        self._require_client()
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            response = await self.client.blocks.children.list(block_id=page_id, start_cursor=cursor)
            blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return blocks

    async def replace_auto_dashboard_blocks(self, *, page_id: str, markdown: str) -> int:
        self._require_client()
        blocks = await self.list_child_blocks(page_id)
        to_delete: list[str] = []
        deleting = False
        for block in blocks:
            block_text = block_to_text(block)
            if block_text.startswith("## [AUTO_DASHBOARD]") or block_text.startswith("# [AUTO_DASHBOARD]"):
                deleting = True
                to_delete.append(block["id"])
                continue
            if deleting:
                to_delete.append(block["id"])
                if block.get("type") == "divider":
                    deleting = False

        # Phase 4: Batch delete — parallel deletion in chunks of 10
        BATCH_SIZE = 10
        for i in range(0, len(to_delete), BATCH_SIZE):
            batch = to_delete[i : i + BATCH_SIZE]
            await asyncio.gather(*(self.client.blocks.delete(block_id=bid) for bid in batch))

        new_blocks = markdown_to_blocks(markdown)
        if new_blocks:
            await self.client.blocks.children.append(block_id=page_id, children=new_blocks)
        return len(new_blocks)

    async def _collect_block_text(self, block_id: str, *, max_depth: int) -> list[str]:
        if max_depth < 0:
            return []
        self._require_client()
        blocks = await self.list_child_blocks(block_id)
        lines: list[str] = []
        for block in blocks:
            text = block_to_text(block)
            if text:
                lines.append(text)
            if block.get("has_children") and max_depth > 0:
                lines.extend(await self._collect_block_text(block["id"], max_depth=max_depth - 1))
        return lines

    def _to_page_summary(self, page: dict[str, Any]) -> PageSummary:
        properties = page.get("properties", {})
        title = "Untitled"
        for prop in properties.values():
            if prop.get("type") != "title":
                continue
            title_items = prop.get("title", [])
            if title_items:
                title = title_items[0].get("plain_text", "Untitled")
            break
        return PageSummary(
            id=page.get("id", ""),
            title=title,
            url=page.get("url", ""),
            last_edited_time=page.get("last_edited_time", ""),
            object_type=page.get("object", "page"),
        )

    def _require_client(self) -> None:
        if self.client is None:
            raise NotionAdapterError("notion_not_configured", "NOTION_API_KEY is missing.")
