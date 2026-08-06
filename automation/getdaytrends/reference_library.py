"""Local reference library for creator research.

The library deliberately stores user-curated metadata only. It never fetches,
downloads, or republishes remote content. Platform collectors can be connected
later without coupling the dashboard to third-party credentials.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

Platform = Literal["youtube", "instagram", "tiktok", "threads", "x", "other"]
ContentFormat = Literal["short", "long", "reel", "carousel", "post", "thread", "other"]

_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "igshid", "si"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonicalize_source_url(value: str) -> str:
    """Validate a remote URL and remove known tracking-only parameters."""
    candidate = value.strip()
    parts = urlsplit(candidate)
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("source_url must be an absolute http(s) URL")

    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_KEYS
    ]
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


class ReferenceItemCreate(BaseModel):
    """Metadata accepted when a creator adds a reference."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=240)
    source_url: str = Field(min_length=1, max_length=2048)
    platform: Platform
    creator: str = Field(default="", max_length=160)
    keyword: str = Field(default="", max_length=160)
    content_format: ContentFormat = "other"
    recommendation_score: int = Field(default=0, ge=0, le=100)
    published_at: str = Field(default="", max_length=80)
    source_id: str = Field(default="", max_length=240)
    caption: str = Field(default="", max_length=20_000)
    transcript: str = Field(default="", max_length=100_000)
    translated_text: str = Field(default="", max_length=100_000)
    summary: str = Field(default="", max_length=20_000)
    memo: str = Field(default="", max_length=10_000)
    saved: bool = False
    read: bool = False

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return canonicalize_source_url(value)


class ReferenceItemPatch(BaseModel):
    """Mutable creator-review fields for an existing reference."""

    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation_score: int | None = Field(default=None, ge=0, le=100)
    caption: str | None = Field(default=None, max_length=20_000)
    transcript: str | None = Field(default=None, max_length=100_000)
    translated_text: str | None = Field(default=None, max_length=100_000)
    summary: str | None = Field(default=None, max_length=20_000)
    memo: str | None = Field(default=None, max_length=10_000)
    saved: bool | None = None
    read: bool | None = None


class DuplicateReferenceError(ValueError):
    """Raised when the same canonical source is already in the library."""


class ReferenceLibraryStore:
    """Small atomic JSON store for local-only reference metadata."""

    version = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _empty_payload(self) -> dict:
        return {"version": self.version, "items": []}

    def _read_unlocked(self) -> dict:
        if not self.path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("reference library file is unreadable") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("reference library file has an invalid shape")
        return payload

    def _write_unlocked(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    def create(self, value: ReferenceItemCreate) -> dict:
        with self._lock:
            payload = self._read_unlocked()
            items = payload["items"]
            for item in items:
                same_url = item.get("source_url") == value.source_url
                same_source_id = bool(value.source_id) and (
                    item.get("platform") == value.platform and item.get("source_id") == value.source_id
                )
                if same_url or same_source_id:
                    raise DuplicateReferenceError("reference already exists")

            timestamp = _utc_now()
            item = {
                "id": uuid4().hex,
                **value.model_dump(),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            items.append(item)
            self._write_unlocked(payload)
            return dict(item)

    def upsert_live(self, value: ReferenceItemCreate) -> tuple[dict, bool]:
        """Insert a live result or refresh its non-user metadata."""
        with self._lock:
            payload = self._read_unlocked()
            for item in payload["items"]:
                same_url = item.get("source_url") == value.source_url
                same_source_id = bool(value.source_id) and (
                    item.get("platform") == value.platform and item.get("source_id") == value.source_id
                )
                if not (same_url or same_source_id):
                    continue

                incoming = value.model_dump()
                for field in ("title", "creator", "content_format", "published_at", "source_id", "caption"):
                    if incoming.get(field):
                        item[field] = incoming[field]
                if not item.get("keyword") and incoming.get("keyword"):
                    item["keyword"] = incoming["keyword"]
                item["recommendation_score"] = max(
                    int(item.get("recommendation_score") or 0),
                    int(incoming.get("recommendation_score") or 0),
                )
                item["updated_at"] = _utc_now()
                self._write_unlocked(payload)
                return dict(item), False

            timestamp = _utc_now()
            item = {
                "id": uuid4().hex,
                **value.model_dump(),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            payload["items"].append(item)
            self._write_unlocked(payload)
            return dict(item), True

    def get(self, item_id: str) -> dict:
        with self._lock:
            for item in self._read_unlocked()["items"]:
                if item.get("id") == item_id:
                    return dict(item)
        raise KeyError(item_id)

    def list(
        self,
        *,
        query: str = "",
        platform: str = "",
        content_format: str = "",
        saved: bool | None = None,
        read: bool | None = None,
        min_score: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        needle = query.strip().casefold()
        searchable_fields = (
            "title",
            "creator",
            "keyword",
            "caption",
            "transcript",
            "translated_text",
            "summary",
            "memo",
        )
        with self._lock:
            items = [dict(item) for item in self._read_unlocked()["items"]]

        def matches(item: dict) -> bool:
            if platform and item.get("platform") != platform:
                return False
            if content_format and item.get("content_format") != content_format:
                return False
            if saved is not None and bool(item.get("saved")) is not saved:
                return False
            if read is not None and bool(item.get("read")) is not read:
                return False
            if int(item.get("recommendation_score") or 0) < min_score:
                return False
            return not needle or any(
                needle in str(item.get(field, "")).casefold() for field in searchable_fields
            )

        filtered = [item for item in items if matches(item)]
        filtered.sort(
            key=lambda item: (int(item.get("recommendation_score") or 0), item.get("updated_at", "")),
            reverse=True,
        )
        return filtered[:limit]

    def update(self, item_id: str, patch: ReferenceItemPatch) -> dict:
        changes = patch.model_dump(exclude_unset=True, exclude_none=True)
        with self._lock:
            payload = self._read_unlocked()
            for item in payload["items"]:
                if item.get("id") != item_id:
                    continue
                item.update(changes)
                item["updated_at"] = _utc_now()
                self._write_unlocked(payload)
                return dict(item)
        raise KeyError(item_id)

    def stats(self) -> dict:
        with self._lock:
            items = [dict(item) for item in self._read_unlocked()["items"]]
        by_platform: dict[str, int] = {}
        for item in items:
            platform = str(item.get("platform") or "other")
            by_platform[platform] = by_platform.get(platform, 0) + 1
        return {
            "total": len(items),
            "saved": sum(bool(item.get("saved")) for item in items),
            "unread": sum(not bool(item.get("read")) for item in items),
            "recommended": sum(int(item.get("recommendation_score") or 0) >= 80 for item in items),
            "by_platform": dict(sorted(by_platform.items())),
        }

    def get_live_status(self) -> dict:
        with self._lock:
            status = self._read_unlocked().get("live_status", {})
        return dict(status) if isinstance(status, dict) else {}

    def set_live_status(self, status: dict) -> dict:
        with self._lock:
            payload = self._read_unlocked()
            payload["live_status"] = dict(status)
            self._write_unlocked(payload)
            return dict(payload["live_status"])
