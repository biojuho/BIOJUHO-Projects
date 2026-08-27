"""Live public-metadata collector for the creator reference library."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import shutil
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    from .reference_library import (
        ReferenceItemCreate,
        ReferenceLibraryStore,
        canonicalize_source_url,
    )
except ImportError:
    from reference_library import (
        ReferenceItemCreate,
        ReferenceLibraryStore,
        canonicalize_source_url,
    )


DEFAULT_LIVE_KEYWORDS = ["AI 콘텐츠", "유튜브 성장", "콘텐츠 마케팅"]
DEFAULT_RECENT_DAYS = 14
DEFAULT_MAX_AGE_HOURS = 14 * 24.0  # 336.0 hours

SPAM_PATTERNS = (
    "바카라",
    "토토",
    "홀덤",
    "카지노",
    "불법",
    "사설토토",
    "대출상담",
    "성인용품",
    "조건만남",
    "카톡상담",
    "텔레그램",
    "재테크사기",
    "무료리딩방",
    "슬롯머신",
    "먹튀",
    "야동",
    "폰테크",
    "코인리딩",
    "fx마진",
)

_DEFAULT_KEYWORD_TITLE_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "ai 콘텐츠": (
        ("ai", "인공지능", "생성형", "chatgpt", "챗gpt"),
        ("콘텐츠", "영상", "이미지", "제작", "크리에이터"),
    ),
    "유튜브 성장": (
        ("유튜브", "youtube", "채널", "구독자", "쇼츠", "shorts", "조회수"),
        ("성장", "키우", "늘리", "알고리즘", "노출", "수익", "떡상", "조회"),
    ),
    "콘텐츠 마케팅": (
        ("콘텐츠", "영상", "브랜드", "광고", "크리에이터"),
        ("마케팅", "홍보", "전환", "고객", "세일즈", "퍼널"),
    ),
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_iso(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(candidate)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _format_duration(seconds: float | int | None) -> str:
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _calculate_age_and_vph(
    published_dt: datetime | None,
    views: int,
    now: datetime | None = None,
) -> tuple[float | None, str, float | None]:
    if published_dt is None:
        return None, "게시시각 미확인", None

    current = now or datetime.now(UTC)
    age_seconds = max(0.0, (current - published_dt).total_seconds())
    age_hours = round(age_seconds / 3600.0, 1)

    if age_hours < 1.0:
        minutes = max(1, int(age_seconds / 60))
        age_text = f"{minutes}분 전"
    elif age_hours < 24.0:
        age_text = f"{int(age_hours)}시간 전"
    elif age_hours < 24.0 * 30.0:
        days = max(1, int(age_hours / 24.0))
        age_text = f"{days}일 전"
    elif age_hours < 24.0 * 365.0:
        months = max(1, int(age_hours / (24.0 * 30.0)))
        age_text = f"{months}달 전"
    else:
        years = max(1, int(age_hours / (24.0 * 365.0)))
        age_text = f"{years}년 전"

    vph = round(views / max(1.0, age_hours), 1)
    return age_hours, age_text, vph


def _compute_topic_relevance(
    title: str,
    description: str,
    tags: list[str] | None,
    keyword: str,
) -> int:
    kw_clean = keyword.strip().lower()
    if not kw_clean:
        return 50

    title_lower = title.lower()
    desc_lower = description[:1000].lower()
    tags_lower = [str(tag).lower() for tag in (tags or [])]

    if kw_clean in title_lower:
        return 95

    kw_terms = [term for term in kw_clean.split() if term]
    if kw_terms and all(term in title_lower for term in kw_terms):
        return 85
    if kw_terms and any(term in title_lower for term in kw_terms):
        return 40
    if any(kw_clean in tag or all(t in tag for t in kw_terms) for tag in tags_lower):
        return 55
    if kw_clean in desc_lower or (kw_terms and all(term in desc_lower for term in kw_terms)):
        return 50
    if kw_terms and any(term in desc_lower for term in kw_terms):
        return 40

    return 20


def _title_matches_keyword(title: str, keyword: str) -> bool:
    """Require visible title evidence before velocity can promote a video.

    YouTube search treats multi-word Korean queries loosely.  In live probes,
    ``유튜브 성장`` returned cloud-computing growth and generic workplace clips.
    The three default queries therefore use small intent groups; custom queries
    require every entered term in the title.  This is deliberately conservative:
    a private reference queue is useful only when its topic is obvious at a glance.
    """
    title_lower = title.strip().lower()
    keyword_lower = keyword.strip().lower()
    if not title_lower or not keyword_lower:
        return False
    if keyword_lower in title_lower:
        return True

    groups = _DEFAULT_KEYWORD_TITLE_GROUPS.get(keyword_lower)
    if groups is not None:
        return all(any(alias in title_lower for alias in group) for group in groups)

    terms = [term for term in keyword_lower.split() if term]
    return bool(terms) and all(term in title_lower for term in terms)


def _is_spam_or_excluded(title: str, channel: str, description: str) -> bool:
    text_to_check = f"{title} {channel} {description[:500]}".lower()
    return any(pattern in text_to_check for pattern in SPAM_PATTERNS)


def _generate_recommendation(
    views: int,
    vph: float | None,
    age_hours: float | None,
    age_text: str,
    likes: int,
    comments: int,
    duration: int,
    topic_relevance: int,
    keyword: str,
    recency_verified: bool = True,
) -> tuple[int, str]:
    # 1. Freshness signal (0 to 35)
    if not recency_verified or age_hours is None:
        freshness_signal = 5
    elif age_hours <= 12.0:
        freshness_signal = 35
    elif age_hours <= 24.0:
        freshness_signal = 30
    elif age_hours <= 72.0:
        freshness_signal = 22
    elif age_hours <= 168.0:  # 7 days
        freshness_signal = 15
    elif age_hours <= 336.0:  # 14 days
        freshness_signal = 8
    else:
        freshness_signal = 0

    # 2. Velocity signal (0 to 30)
    if vph is None or vph <= 0:
        velocity_signal = 0
    elif vph >= 5000.0:
        velocity_signal = 30
    elif vph >= 1000.0:
        velocity_signal = 25
    elif vph >= 300.0:
        velocity_signal = 20
    elif vph >= 100.0:
        velocity_signal = 15
    elif vph >= 20.0:
        velocity_signal = 10
    else:
        velocity_signal = 5

    # 3. Engagement signal (0 to 20)
    engagement_signal = 0
    if views > 0:
        like_ratio = (likes / views) * 100.0
        comment_ratio = (comments / views) * 100.0
        if like_ratio >= 4.0:
            engagement_signal += 10
        elif like_ratio >= 2.0:
            engagement_signal += 6
        elif likes > 0:
            engagement_signal += 3

        if comment_ratio >= 0.5:
            engagement_signal += 10
        elif comment_ratio >= 0.2:
            engagement_signal += 6
        elif comments > 0:
            engagement_signal += 3
    engagement_signal = min(20, engagement_signal)

    # 4. Topic relevance signal (0 to 15)
    relevance_signal = min(15, round(topic_relevance * 0.15))

    # 5. Format bonus
    format_bonus = 5 if 0 < duration <= 60 else 0

    raw_score = 15 + freshness_signal + velocity_signal + engagement_signal + relevance_signal + format_bonus

    # Cap unverified items to avoid false top rankings (고점 방지)
    if not recency_verified:
        score = min(45, max(10, raw_score))
    else:
        score = min(100, max(10, raw_score))

    # Construct recommendation reason
    if not recency_verified:
        reason = f"'{keyword}' 관련 참고 영상 (게시시각 미확인)"
    elif vph is not None and vph >= 300.0:
        content_type = "쇼츠" if 0 < duration <= 60 else "영상"
        reason = f"게시 {age_text} 만에 시간당 조회 {int(vph):,}회 기록한 급상승 {content_type}"
    elif comments >= 50 or likes >= 500:
        reason = f"게시 {age_text}, 좋아요 {likes:,}개·댓글 {comments:,}개로 높은 시청자 반응"
    elif age_hours is not None and age_hours <= 48.0:
        reason = f"최근 업로드({age_text}) 및 '{keyword}' 핵심 주제 일치"
    elif views >= 10_000:
        reason = f"최근 14일 조회수 {views:,}회 달성한 '{keyword}' 레퍼런스 포맷"
    else:
        reason = f"'{keyword}' 관련 최신 콘텐츠 레퍼런스 ({age_text})"

    return score, reason


def _recommendation_score(entry: dict[str, Any], position: int = 0) -> int:
    views = max(0, int(entry.get("view_count") or 0))
    duration = max(0, int(entry.get("duration") or 0))
    view_signal = min(35, round(math.log10(views + 1) * 6))
    position_signal = max(0, 18 - position * 3)
    format_signal = 8 if 0 < duration <= 60 else 4
    return min(100, 38 + view_signal + position_signal + format_signal)


class YouTubeLiveReferenceCollector:
    """Search recent YouTube metadata through yt-dlp with metadata-only enrichment."""

    def __init__(
        self,
        store: ReferenceLibraryStore,
        executable: str | None = None,
        timeout: float = 25.0,
        per_item_timeout: float = 12.0,
        recent_days: int = DEFAULT_RECENT_DAYS,
    ):
        self.store = store
        self.executable = executable if executable is not None else shutil.which("yt-dlp")
        self.timeout = timeout
        self.per_item_timeout = per_item_timeout
        self.recent_days = recent_days
        self._refresh_lock = asyncio.Lock()
        self._last_good_items: list[dict] = []
        self._last_success_at: str | None = None

    def capabilities(self) -> dict:
        return {
            "youtube": {"available": bool(self.executable), "mode": "public_metadata"},
            "instagram": {"available": False, "mode": "official_api_required"},
            "tiktok": {"available": False, "mode": "official_api_required"},
            "threads": {"available": False, "mode": "official_api_required"},
            "x": {"available": False, "mode": "official_api_required"},
        }

    async def _safe_run_subprocess(self, cmd: list[str], timeout: float) -> tuple[int, bytes, bytes]:
        """Execute a subprocess and guarantee child process cleanup on timeout/cancellation."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return process.returncode or 0, stdout, stderr
        except (TimeoutError, asyncio.CancelledError, Exception):
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                with contextlib.suppress(Exception):
                    await process.communicate()
            raise

    async def _fetch_detailed_metadata(self, source_url: str) -> dict | None:
        """Fetch metadata-only JSON without downloading video/audio/subtitles/thumbnails."""
        if not self.executable:
            return None
        cmd = [
            self.executable,
            "--dump-single-json",
            "--no-warnings",
            "--skip-download",
            "--no-playlist",
            source_url,
        ]
        try:
            returncode, stdout, _ = await self._safe_run_subprocess(cmd, timeout=self.per_item_timeout)
            if returncode == 0 and stdout:
                payload = json.loads(stdout.decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
        except Exception:
            pass
        return None

    async def _search_keyword(self, keyword: str, limit: int, recent_days: int = DEFAULT_RECENT_DAYS) -> list[dict]:
        """Search recent YouTube items using after:YYYY-MM-DD date condition with fallback."""
        if not self.executable:
            return []

        now_utc = datetime.now(UTC)
        cutoff_date = (now_utc - timedelta(days=recent_days)).strftime("%Y-%m-%d")
        query_with_date = f"{keyword} after:{cutoff_date}"
        candidate_limit = search_candidate_count(limit)

        # 1. Primary: Date-sorted search URL (sp=CAI%253D) with after:YYYY-MM-DD query
        quoted_kw = urllib.parse.quote_plus(query_with_date)
        date_search_url = f"https://www.youtube.com/results?search_query={quoted_kw}&sp=CAI%253D"
        cmd1 = [
            self.executable,
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            "--playlist-items",
            f"1:{candidate_limit}",
            date_search_url,
        ]
        try:
            returncode, stdout, _ = await self._safe_run_subprocess(cmd1, timeout=self.timeout)
            if returncode == 0 and stdout:
                payload = json.loads(stdout.decode("utf-8"))
                entries = payload.get("entries", [])
                valid = [entry for entry in entries if isinstance(entry, dict)]
                if valid:
                    return valid
        except Exception:
            pass

        # 2. Fallback: ytsearchN with after:YYYY-MM-DD query
        fallback_query = f"ytsearch{candidate_limit}:{query_with_date}"
        cmd2 = [
            self.executable,
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            fallback_query,
        ]
        try:
            returncode2, stdout2, stderr2 = await self._safe_run_subprocess(cmd2, timeout=self.timeout)
        except TimeoutError:
            raise RuntimeError(f"YouTube search timed out: {query_with_date}") from None

        if returncode2 != 0:
            message = stderr2.decode("utf-8", errors="replace").strip().splitlines()
            reason = message[-1][:240] if message else "unknown yt-dlp error"
            raise RuntimeError(f"YouTube search failed: {reason}")

        try:
            payload2 = json.loads(stdout2.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("YouTube search returned invalid metadata") from exc

        entries2 = payload2.get("entries", [])
        return [entry for entry in entries2 if isinstance(entry, dict)]

    async def _enrich_candidate(
        self,
        entry: dict,
        keyword: str,
        prev_keys: set[str],
        max_age_hours: float,
        now: datetime | None = None,
    ) -> tuple[dict | None, bool]:
        """Enrich candidate metadata and strictly exclude items exceeding max_age_hours.

        Returns (item_dict, was_excluded_for_age: bool).
        """
        video_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        source_url = str(entry.get("url") or entry.get("webpage_url") or "").strip()
        if not video_id or not title:
            return None, False
        if not source_url.startswith(("http://", "https://")):
            source_url = f"https://www.youtube.com/watch?v={video_id}"

        canonical_url = canonicalize_source_url(source_url)
        channel = str(entry.get("channel") or entry.get("uploader") or "").strip()
        description = str(entry.get("description") or "").strip()

        # Spam exclusion check
        if _is_spam_or_excluded(title, channel, description):
            return None, False

        # Check if detailed metadata already present or fetch it
        has_rich_metadata = (
            entry.get("timestamp") is not None
            or entry.get("upload_date") is not None
            or entry.get("like_count") is not None
            or entry.get("published_at") is not None
        )

        detail = None
        if not has_rich_metadata and self.executable:
            detail = await self._fetch_detailed_metadata(canonical_url)

        merged = dict(entry)
        if detail and isinstance(detail, dict):
            merged.update(detail)
            desc_detail = str(detail.get("description") or "").strip()
            if _is_spam_or_excluded(title, channel, desc_detail):
                return None, False

        # Parse published_at
        published_dt: datetime | None = None
        published_at_str = ""
        ts = merged.get("timestamp") or merged.get("release_timestamp")
        if ts and isinstance(ts, (int, float)):
            try:
                published_dt = datetime.fromtimestamp(float(ts), UTC)
                published_at_str = published_dt.isoformat()
            except (ValueError, OSError):
                pass

        if not published_dt and merged.get("upload_date"):
            upload_date_str = str(merged.get("upload_date")).strip()
            if len(upload_date_str) == 8 and upload_date_str.isdigit():
                try:
                    published_dt = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=UTC)
                    published_at_str = published_dt.isoformat()
                except ValueError:
                    pass

        if not published_dt and merged.get("published_at"):
            try:
                parsed_dt = _parse_iso(str(merged["published_at"]))
                if parsed_dt:
                    published_dt = parsed_dt
                    published_at_str = published_dt.isoformat()
            except Exception:
                pass

        views = max(0, int(merged.get("view_count") or 0))
        likes = int(merged.get("like_count") or 0) if merged.get("like_count") is not None else 0
        comments = int(merged.get("comment_count") or 0) if merged.get("comment_count") is not None else 0
        duration = max(0, int(merged.get("duration") or 0))

        age_hours, age_text, vph = _calculate_age_and_vph(published_dt, views, now=now)
        recency_verified = published_dt is not None

        # Strictly exclude items older than max_age_hours (e.g. > 336.0h = 14 days)
        if age_hours is not None and age_hours > max_age_hours:
            return None, True

        topic_relevance = _compute_topic_relevance(
            title,
            str(merged.get("description") or ""),
            merged.get("tags"),
            keyword,
        )

        rec_score, rec_reason = _generate_recommendation(
            views=views,
            vph=vph,
            age_hours=age_hours,
            age_text=age_text,
            likes=likes,
            comments=comments,
            duration=duration,
            topic_relevance=topic_relevance,
            keyword=keyword,
            recency_verified=recency_verified,
        )

        item_key = video_id or canonical_url
        is_new = item_key not in prev_keys
        content_format = "short" if 0 < duration <= 60 else ("long" if duration > 60 else "other")

        vph_str = f" (VPH {int(vph):,})" if vph is not None else ""
        caption = f"YouTube 라이브 검색 · 조회수 {views:,}{vph_str} · {age_text} · 길이 {_format_duration(duration)}"

        item = {
            "id": video_id,
            "source_id": video_id,
            "title": title,
            "source_url": canonical_url,
            "platform": "youtube",
            "creator": channel,
            "channel": channel,
            "keyword": keyword,
            "content_format": content_format,
            "published_at": published_at_str,
            "recency_verified": recency_verified,
            "age_hours": age_hours,
            "age_text": age_text,
            "view_count": views,
            "views": views,
            "views_per_hour": vph,
            "vph": vph,
            "like_count": likes,
            "likes": likes,
            "comment_count": comments,
            "comments": comments,
            "duration": duration,
            "duration_formatted": _format_duration(duration),
            "topic_relevance": topic_relevance,
            "recommendation_score": rec_score,
            "recommendation_reason": rec_reason,
            "is_new": is_new,
            "status": "new" if is_new else "repeat",
            "caption": caption,
            "summary": str(merged.get("description") or "")[:300],
            "saved": False,
            "read": False,
        }
        return item, False

    def _to_reference(self, entry: dict, keyword: str, position: int = 0) -> ReferenceItemCreate | None:
        """Compatibility helper to convert an entry to ReferenceItemCreate."""
        video_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        source_url = str(entry.get("url") or entry.get("webpage_url") or "").strip()
        if not video_id or not title:
            return None
        if not source_url.startswith(("http://", "https://")):
            source_url = f"https://www.youtube.com/watch?v={video_id}"

        duration = max(0, int(entry.get("duration") or 0))
        views = max(0, int(entry.get("view_count") or 0))
        channel = str(entry.get("channel") or entry.get("uploader") or "").strip()
        published_at = str(entry.get("published_at") or "")
        rec_score = entry.get("recommendation_score") or _recommendation_score(entry, position)
        caption = entry.get("caption") or f"YouTube 라이브 검색 · 조회수 {views:,} · 길이 {_format_duration(duration)}"

        return ReferenceItemCreate(
            title=title,
            source_url=source_url,
            platform="youtube",
            creator=channel,
            keyword=keyword,
            content_format="short" if 0 < duration <= 60 else "long",
            recommendation_score=rec_score,
            published_at=published_at,
            source_id=video_id,
            caption=caption,
            summary=str(entry.get("summary") or entry.get("description") or "")[:300],
        )

    async def _invoke_search(self, kw: str, limit: int, recent_days: int) -> list[dict]:
        try:
            return await self._search_keyword(kw, limit, recent_days=recent_days)
        except TypeError:
            return await self._search_keyword(kw, limit)

    async def refresh(
        self,
        keywords: list[str] | None = None,
        per_keyword: int = 5,
        recent_days: int | None = None,
    ) -> dict:
        normalized: list[str] = []
        if keywords:
            for keyword in keywords:
                value = str(keyword).strip()
                if value and value.casefold() not in {item.casefold() for item in normalized}:
                    normalized.append(value)
        normalized = normalized[:5] or list(DEFAULT_LIVE_KEYWORDS)
        per_keyword = min(10, max(1, int(per_keyword)))
        effective_recent_days = recent_days if recent_days is not None else self.recent_days
        max_age_hours = effective_recent_days * 24.0

        async with self._refresh_lock:
            prev_status = self.store.get_live_status()
            prev_items = prev_status.get("items") or self._last_good_items or []
            prev_keys = {
                str(item.get("source_id") or item.get("id") or item.get("source_url") or "").strip()
                for item in prev_items
                if isinstance(item, dict)
            }
            prev_keys.discard("")

            now_iso = _utc_now()

            if not self.executable:
                preserved_items = [dict(it) for it in (self._last_good_items or prev_items)]
                last_success = self._last_success_at or prev_status.get("last_success_at")
                status = {
                    "available": False,
                    "source": "youtube",
                    "keywords": normalized,
                    "recent_days": effective_recent_days,
                    "max_age_hours": int(max_age_hours),
                    "excluded_old_count": 0,
                    "excluded_irrelevant_count": 0,
                    "collected": len(preserved_items),
                    "new_count": 0,
                    "repeat_count": len(preserved_items),
                    "created": 0,
                    "updated": 0,
                    "items": preserved_items,
                    "last_success_at": last_success,
                    "last_attempt_at": now_iso,
                    "errors": ["yt-dlp executable is not installed"],
                    "is_stale": True,
                    "refreshed_at": now_iso,
                    "capabilities": self.capabilities(),
                }
                return self.store.set_live_status(status)

            # Search each keyword concurrently with after:YYYY-MM-DD condition
            search_results = await asyncio.gather(
                *(self._invoke_search(kw, per_keyword, recent_days=effective_recent_days) for kw in normalized),
                return_exceptions=True,
            )

            all_collected_items: list[dict] = []
            errors: list[str] = []
            seen_item_keys: set[str] = set()
            excluded_old_count = 0
            excluded_irrelevant_count = 0

            for keyword, result in zip(normalized, search_results, strict=True):
                if isinstance(result, Exception):
                    errors.append(f"[{keyword}] {str(result)[:240]}")
                    continue

                raw_candidates = [entry for entry in result if isinstance(entry, dict)]
                matching_candidates = [
                    entry
                    for entry in raw_candidates
                    if _title_matches_keyword(str(entry.get("title") or ""), keyword)
                ]
                excluded_irrelevant_count += len(raw_candidates) - len(matching_candidates)
                candidates = matching_candidates[: limit_candidate_count(per_keyword)]
                enrichment_tasks = [
                    self._enrich_candidate(entry, keyword, prev_keys, max_age_hours=max_age_hours)
                    for entry in candidates
                ]
                enriched_results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

                eligible_for_keyword: list[dict] = []
                for res in enriched_results:
                    if isinstance(res, Exception):
                        continue
                    enriched, was_excluded_for_age = res
                    if was_excluded_for_age:
                        excluded_old_count += 1
                        continue
                    if enriched is None:
                        continue

                    eligible_for_keyword.append(enriched)

                eligible_for_keyword.sort(
                    key=lambda item: (
                        int(item.get("recommendation_score") or 0),
                        float(item.get("views_per_hour") or 0),
                        int(item.get("view_count") or 0),
                    ),
                    reverse=True,
                )
                accepted_for_keyword = 0
                for enriched in eligible_for_keyword:

                    item_key = str(
                        enriched.get("source_id")
                        or enriched.get("id")
                        or enriched.get("source_url")
                        or ""
                    ).strip()
                    if item_key and item_key in seen_item_keys:
                        continue
                    if accepted_for_keyword >= per_keyword:
                        continue
                    if item_key:
                        seen_item_keys.add(item_key)
                    all_collected_items.append(enriched)
                    accepted_for_keyword += 1

            now_iso = _utc_now()

            # At least one item successfully collected
            if all_collected_items:
                all_collected_items.sort(
                    key=lambda x: (
                        int(x.get("recommendation_score") or 0),
                        float(x.get("views_per_hour") or 0),
                        int(x.get("view_count") or 0),
                    ),
                    reverse=True,
                )

                new_count = sum(1 for item in all_collected_items if item.get("is_new"))
                repeat_count = len(all_collected_items) - new_count

                self._last_good_items = [dict(it) for it in all_collected_items]
                self._last_success_at = now_iso

                status = {
                    "available": True,
                    "source": "youtube",
                    "keywords": normalized,
                    "recent_days": effective_recent_days,
                    "max_age_hours": int(max_age_hours),
                    "excluded_old_count": excluded_old_count,
                    "excluded_irrelevant_count": excluded_irrelevant_count,
                    "collected": len(all_collected_items),
                    "new_count": new_count,
                    "repeat_count": repeat_count,
                    "created": 0,
                    "updated": 0,
                    "items": all_collected_items,
                    "last_success_at": self._last_success_at,
                    "last_attempt_at": now_iso,
                    "errors": errors,
                    "is_stale": False,
                    "refreshed_at": now_iso,
                    "capabilities": self.capabilities(),
                }
                return self.store.set_live_status(status)

            # Transient Full Failure (0 items collected and errors present)
            preserved_items = [dict(it) for it in (self._last_good_items or prev_items)]
            last_success = self._last_success_at or prev_status.get("last_success_at")

            status = {
                "available": True,
                "source": "youtube",
                "keywords": normalized,
                "recent_days": effective_recent_days,
                "max_age_hours": int(max_age_hours),
                "excluded_old_count": excluded_old_count,
                "excluded_irrelevant_count": excluded_irrelevant_count,
                "collected": len(preserved_items),
                "new_count": 0,
                "repeat_count": len(preserved_items),
                "created": 0,
                "updated": 0,
                "items": preserved_items,
                "last_success_at": last_success,
                "last_attempt_at": now_iso,
                "errors": errors if errors else ["No recent candidates returned for keywords"],
                "is_stale": True,
                "refreshed_at": now_iso,
                "capabilities": self.capabilities(),
            }
            return self.store.set_live_status(status)


def limit_candidate_count(per_keyword: int) -> int:
    return max(1, min(20, per_keyword * 2))


def search_candidate_count(per_keyword: int) -> int:
    """Inspect enough flat titles to replace loose-search false positives."""
    return max(6, min(30, per_keyword * 6))
