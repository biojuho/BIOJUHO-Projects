from __future__ import annotations

import re
import urllib.parse
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger as log

from utils import run_async

_SHORT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)

# 브라우저 UA 위장 금지(Reddit Public Content Policy). 403이어도 이 문자열을 바꾸지 않는다.
_USER_AGENT = "biojuho-x-radar/1.0 (research collector; not a browser)"


class RedditFetchError(RuntimeError):
    """HTTP 실패를 빈 목록으로 접지 않고 상류 errors에 남긴다."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Reddit HTTP {status_code}: {url}")

# 0074 첨부 규약 (direct_community_sources.py와 동일 필드명/값)
_ATTACHMENT_VIDEO = "video"
_ATTACHMENT_IMAGE = "image"
_ATTACHMENT_TEXT = "text"
_ATTACHMENT_UNKNOWN = "unknown"

_HANGUL_PATTERN = re.compile(r"[가-힣]")
_TITLE_VIDEO_SUFFIX_RE = re.compile(r"\.(mp4|webm|mov|avi|mkv|wmv)\b", re.IGNORECASE)
_TITLE_IMAGE_SUFFIX_RE = re.compile(r"\.(jpe?g|png|gif|bmp|webp)\b", re.IGNORECASE)
_VIDEO_DOMAINS = {"v.redd.it", "youtube.com", "youtu.be", "tiktok.com", "streamable.com", "clips.twitch.tv"}
_IMAGE_DOMAINS = {"i.redd.it", "i.imgur.com", "imgur.com"}


def _resolve_timeout(timeout: httpx.Timeout | float | None) -> httpx.Timeout | float:
    return _SHORT_TIMEOUT if timeout is None else timeout


def _has_hangul(text: str) -> bool:
    return bool(_HANGUL_PATTERN.search(str(text or "")))


def _attachment_fields(kind: str, *, video_url: str = "") -> dict[str, str]:
    return {
        "attachment_kind": kind,
        "video_url": video_url if kind == _ATTACHMENT_VIDEO and video_url else "",
    }


def _reddit_attachment_info(data: dict[str, Any]) -> tuple[str, str]:
    """Reddit 포스트의 첨부 형태(video/image/text/unknown)와 비디오 링크를 추출한다.

    주의: 미디어 파일 다운로드는 절대 수행하지 않고, 링크 및 사실 여부만 전달한다(Storyful 10계율).
    """
    is_video = bool(data.get("is_video"))
    post_hint = str(data.get("post_hint") or "").lower()
    domain = str(data.get("domain") or "").lower()
    url = str(data.get("url") or "")
    title = str(data.get("title") or "")
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    secure_media = data.get("secure_media") if isinstance(data.get("secure_media"), dict) else {}
    preview = data.get("preview") if isinstance(data.get("preview"), dict) else {}

    # 1. 비디오 판정
    video_url = ""
    if is_video or post_hint in ("hosted:video", "rich:video") or domain in _VIDEO_DOMAINS:
        reddit_video = (media.get("reddit_video") or secure_media.get("reddit_video") or {}) if isinstance(media, dict) else {}
        if isinstance(reddit_video, dict) and reddit_video.get("fallback_url"):
            video_url = str(reddit_video.get("fallback_url") or "")
        elif isinstance(preview.get("reddit_video_preview"), dict):
            video_url = str(preview["reddit_video_preview"].get("fallback_url") or "")
        elif _TITLE_VIDEO_SUFFIX_RE.search(url) or domain in _VIDEO_DOMAINS:
            video_url = url
        return _ATTACHMENT_VIDEO, video_url

    if _TITLE_VIDEO_SUFFIX_RE.search(title) or _TITLE_VIDEO_SUFFIX_RE.search(url):
        return _ATTACHMENT_VIDEO, url if _TITLE_VIDEO_SUFFIX_RE.search(url) else ""

    # 2. 이미지 판정
    if (
        post_hint == "image"
        or domain in _IMAGE_DOMAINS
        or _TITLE_IMAGE_SUFFIX_RE.search(url)
        or _TITLE_IMAGE_SUFFIX_RE.search(title)
        or bool(preview.get("images"))
    ):
        return _ATTACHMENT_IMAGE, ""

    # 3. 텍스트 판정
    if data.get("is_self") is True or domain.startswith("self."):
        return _ATTACHMENT_TEXT, ""

    return _ATTACHMENT_UNKNOWN, ""


def _parse_reddit_listing(
    data: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Reddit listing JSON 응답을 정규화된 딕셔너리 리스트로 변환한다."""
    children = data.get("data", {}).get("children", [])
    if not isinstance(children, list):
        return []

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in children:
        if not isinstance(item, dict):
            continue
        d = item.get("data")
        if not isinstance(d, dict):
            continue

        post_id = str(d.get("id") or "").strip()
        title = str(d.get("title") or "").strip()
        if not post_id or not title or post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        subreddit = str(d.get("subreddit") or "").strip()
        permalink = str(d.get("permalink") or "").strip()
        source_url = f"https://www.reddit.com{permalink}" if permalink else str(d.get("url") or "").strip()

        # 시각 추출 (created_utc): 0064 규약 준수 - 없으면 None이며 현재 시각으로 메우지 않는다.
        created_utc = d.get("created_utc")
        source_published_at = None
        if isinstance(created_utc, (int, float)) and created_utc > 0:
            try:
                source_published_at = datetime.fromtimestamp(created_utc, tz=UTC).isoformat()
            except (ValueError, OSError):
                source_published_at = None

        # 첨부 형태
        kind, video_link = _reddit_attachment_info(d)

        # 추천수·댓글수: 사실 그대로 전달하고 점수로 환산하지 않는다(0053 규약).
        votes = int(d.get("score") or d.get("ups") or 0)
        comments = int(d.get("num_comments") or 0)

        # 언어: 스스로 판정하여 배제하지 않고 언어 필드로만 표시
        is_korean = _has_hangul(title)
        language = "ko" if is_korean else "en"

        reasons = [
            f"r/{subreddit} {votes}upvotes · 댓글 {comments}개"
            if subreddit
            else f"Reddit {votes}upvotes · 댓글 {comments}개"
        ]
        if kind == _ATTACHMENT_VIDEO:
            reasons.append("동영상 첨부")
        elif kind == _ATTACHMENT_IMAGE:
            reasons.append("이미지 첨부")

        item_dict: dict[str, Any] = {
            "id": post_id,
            "title": title,
            "keyword": title,
            "url": source_url,
            "source_url": source_url,
            "permalink": f"https://www.reddit.com{permalink}" if permalink else "",
            "subreddit": subreddit,
            "source": f"Reddit (r/{subreddit})" if subreddit else "Reddit",
            "publisher": f"r/{subreddit}" if subreddit else "Reddit",
            "sources": [f"Reddit (r/{subreddit})" if subreddit else "Reddit"],
            "author": str(d.get("author") or "").strip(),
            "votes": votes,
            "comments": comments,
            "source_published_at": source_published_at,
            "published_at": source_published_at,
            "first_seen_at": None,
            "lane": "Reddit 핫 포스트",
            "qualification_mode": "reddit_hot_post",
            "category": "해외 바이럴",
            "language": language,
            "is_korean": is_korean,
            "reasons": reasons,
        }
        item_dict.update(_attachment_fields(kind, video_url=video_link))
        items.append(item_dict)

    return items


async def _async_fetch_reddit_hot(
    session: httpx.AsyncClient,
    limit: int = 20,
    *,
    subreddit: str = "popular",
    timeout: httpx.Timeout | float | None = None,
) -> list[dict[str, Any]]:
    """Reddit 핫 포스트 목록을 수집한다 (비동기)."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    headers = {"User-Agent": _USER_AGENT}

    try:
        resp = await session.get(url, headers=headers, timeout=_resolve_timeout(timeout or _DEFAULT_TIMEOUT))
    except Exception as e:
        log.warning(f"Reddit 핫 포스트 수집 오류 (r/{subreddit}): {e}")
        raise
    if resp.status_code != 200:
        log.warning(f"Reddit 핫 포스트 수집 실패 (status={resp.status_code}): r/{subreddit}")
        raise RedditFetchError(resp.status_code, url)
    data = resp.json()
    return _parse_reddit_listing(data)


async def _async_fetch_reddit_trends(
    session: httpx.AsyncClient,
    keyword: str,
    timeout: httpx.Timeout | float | None = None,
) -> str:
    """Reddit 핫 포스트 수집 (비동기, 키워드 검색 기반 하위 호환)."""
    encoded_query = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={encoded_query}&sort=hot&limit=5&t=day"
    headers = {"User-Agent": _USER_AGENT}

    try:
        resp = await session.get(url, headers=headers, timeout=_resolve_timeout(timeout))
        if resp.status_code != 200:
            log.warning(f"Reddit 검색 수집 실패 (status={resp.status_code}): {keyword}")
            raise RedditFetchError(resp.status_code, url)
        data = resp.json()

        posts = []
        for item in data.get("data", {}).get("children", []):
            d = item["data"]
            posts.append(f"[{d.get('score', 0)}pts] {d['title']}")

        return "\n".join(posts) if posts else "관련 Reddit 게시물 없음"

    except RedditFetchError:
        raise
    except Exception as e:
        log.warning(f"Reddit API 오류 ({keyword}): {e}")
        return f"[Reddit 접근 제한] {keyword} 데이터 없음"


def fetch_reddit_trends(keyword: str) -> str:
    """Reddit 핫 포스트 수집 (동기 호환 래퍼)."""
    return run_async(_async_fetch_reddit_trends_standalone(keyword))


async def _async_fetch_reddit_trends_standalone(keyword: str) -> str:
    async with httpx.AsyncClient() as session:
        return await _async_fetch_reddit_trends(session, keyword)
