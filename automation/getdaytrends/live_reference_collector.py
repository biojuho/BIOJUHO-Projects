"""Live public-metadata collector for the creator reference library."""

from __future__ import annotations

import asyncio
import json
import math
import shutil
from datetime import UTC, datetime
from typing import Any

try:
    from .reference_library import ReferenceItemCreate, ReferenceLibraryStore
except ImportError:
    from reference_library import ReferenceItemCreate, ReferenceLibraryStore


DEFAULT_LIVE_KEYWORDS = ["AI 콘텐츠", "유튜브 성장", "콘텐츠 마케팅"]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _format_duration(seconds: float | int | None) -> str:
    total = max(0, int(seconds or 0))
    minutes, remainder = divmod(total, 60)
    return f"{minutes}:{remainder:02d}"


def _recommendation_score(entry: dict[str, Any], position: int) -> int:
    views = max(0, int(entry.get("view_count") or 0))
    duration = max(0, int(entry.get("duration") or 0))
    view_signal = min(35, round(math.log10(views + 1) * 6))
    position_signal = max(0, 18 - position * 3)
    format_signal = 8 if 0 < duration <= 60 else 4
    return min(100, 38 + view_signal + position_signal + format_signal)


class YouTubeLiveReferenceCollector:
    """Search YouTube metadata through the installed yt-dlp executable."""

    def __init__(self, store: ReferenceLibraryStore, executable: str | None = None):
        self.store = store
        self.executable = executable if executable is not None else shutil.which("yt-dlp")
        self._refresh_lock = asyncio.Lock()

    def capabilities(self) -> dict:
        return {
            "youtube": {"available": bool(self.executable), "mode": "public_metadata"},
            "instagram": {"available": False, "mode": "official_api_required"},
            "tiktok": {"available": False, "mode": "official_api_required"},
            "threads": {"available": False, "mode": "official_api_required"},
            "x": {"available": False, "mode": "official_api_required"},
        }

    async def _search_keyword(self, keyword: str, limit: int) -> list[dict]:
        if not self.executable:
            return []
        process = await asyncio.create_subprocess_exec(
            self.executable,
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            f"ytsearch{limit}:{keyword}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=25)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError(f"YouTube search timed out: {keyword}") from None
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace").strip().splitlines()
            reason = message[-1][:240] if message else "unknown yt-dlp error"
            raise RuntimeError(f"YouTube search failed: {reason}")
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("YouTube search returned invalid metadata") from exc
        entries = payload.get("entries", [])
        return [entry for entry in entries if isinstance(entry, dict)]

    def _to_reference(self, entry: dict, keyword: str, position: int) -> ReferenceItemCreate | None:
        video_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        source_url = str(entry.get("url") or "").strip()
        if not video_id or not title:
            return None
        if not source_url.startswith(("http://", "https://")):
            source_url = f"https://www.youtube.com/watch?v={video_id}"

        duration = max(0, int(entry.get("duration") or 0))
        views = max(0, int(entry.get("view_count") or 0))
        caption = f"YouTube 라이브 검색 · 조회수 {views:,} · 길이 {_format_duration(duration)}"
        return ReferenceItemCreate(
            title=title,
            source_url=source_url,
            platform="youtube",
            creator=str(entry.get("channel") or entry.get("uploader") or "").strip(),
            keyword=keyword,
            content_format="short" if 0 < duration <= 60 else "long",
            recommendation_score=_recommendation_score(entry, position),
            source_id=video_id,
            caption=caption,
        )

    async def refresh(self, keywords: list[str], per_keyword: int = 5) -> dict:
        normalized: list[str] = []
        for keyword in keywords:
            value = str(keyword).strip()
            if value and value.casefold() not in {item.casefold() for item in normalized}:
                normalized.append(value)
        normalized = normalized[:5] or list(DEFAULT_LIVE_KEYWORDS)
        per_keyword = min(10, max(1, int(per_keyword)))

        async with self._refresh_lock:
            if not self.executable:
                status = {
                    "available": False,
                    "source": "youtube",
                    "keywords": normalized,
                    "collected": 0,
                    "created": 0,
                    "updated": 0,
                    "errors": ["yt-dlp executable is not installed"],
                    "refreshed_at": _utc_now(),
                    "capabilities": self.capabilities(),
                }
                return self.store.set_live_status(status)

            results = await asyncio.gather(
                *(self._search_keyword(keyword, per_keyword) for keyword in normalized),
                return_exceptions=True,
            )
            created = 0
            updated = 0
            collected = 0
            errors: list[str] = []
            for keyword, result in zip(normalized, results, strict=True):
                if isinstance(result, Exception):
                    errors.append(str(result)[:300])
                    continue
                for position, entry in enumerate(result):
                    reference = self._to_reference(entry, keyword, position)
                    if reference is None:
                        continue
                    _, was_created = self.store.upsert_live(reference)
                    collected += 1
                    created += int(was_created)
                    updated += int(not was_created)

            status = {
                "available": True,
                "source": "youtube",
                "keywords": normalized,
                "collected": collected,
                "created": created,
                "updated": updated,
                "errors": errors,
                "refreshed_at": _utc_now(),
                "capabilities": self.capabilities(),
            }
            return self.store.set_live_status(status)
