"""Optional official Threads keyword-search signal collector."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

_THREADS_KEYWORD_SEARCH_URL = "https://graph.threads.net/keyword_search"
_THREADS_FIELDS = "id,permalink,username,text,timestamp,is_verified,has_replies"


def _is_recent_timestamp(value: str, *, now: datetime | None = None) -> bool:
    if not value:
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    return reference - parsed.astimezone(UTC) <= timedelta(hours=48)


def _normalize_posts(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("data", []):
        if not isinstance(raw, dict):
            continue
        permalink = str(raw.get("permalink") or "").strip()
        text = str(raw.get("text") or "").strip()
        timestamp = str(raw.get("timestamp") or "").strip()
        if (
            not text
            or permalink in seen
            or urlparse(permalink).scheme not in {"http", "https"}
            or not _is_recent_timestamp(timestamp)
        ):
            continue
        seen.add(permalink)
        posts.append(
            {
                "id": str(raw.get("id") or ""),
                "permalink": permalink,
                "username": str(raw.get("username") or "").strip(),
                "text": text,
                "timestamp": timestamp,
                "is_verified": bool(raw.get("is_verified")),
                "has_replies": bool(raw.get("has_replies")),
            }
        )
        if len(posts) >= limit:
            break
    return posts


class ThreadsSignalCollector:
    """Read recent public Threads posts through Meta's official API."""

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token if access_token is not None else os.getenv("THREADS_ACCESS_TOKEN", "")

    @property
    def available(self) -> bool:
        return bool(self.access_token)

    async def search(
        self,
        session: httpx.AsyncClient,
        keyword: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.access_token:
            return []
        response = await session.get(
            _THREADS_KEYWORD_SEARCH_URL,
            params={
                "q": keyword,
                "search_type": "RECENT",
                "search_mode": "KEYWORD",
                "fields": _THREADS_FIELDS,
                "limit": min(10, max(1, int(limit))),
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        return _normalize_posts(payload, min(10, max(1, int(limit))))
