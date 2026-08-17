"""네이트·줌 뉴스 랭킹 수집기.

제목 전문·링크·소스명만 가져온다. 뉴스 본문은 긁지 않는다(핸드오프 0068 금지사항).
네이트는 euc-kr로 내려올 수 있어 utf-8 → euc-kr 디코딩 폴백을 둔다.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)
_KST = timezone(timedelta(hours=9))

NATE_NEWS_RANKING_URL = "https://news.nate.com/rank/interest?sc=all&p=day"
ZUM_NEWS_RANKING_URL = "https://news.zum.com/"

_NATE_ITEM_RE = re.compile(
    r'<dl class="mduRank rank\d+">\s*<dt><em>(\d+)</em></dt>.*?'
    r'<a href="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_NATE_TITLE_RE = re.compile(r'<(?:h2(?:\s+class="tit")?|span class="tit")[^>]*>(.*?)</(?:h2|span)>', re.S)
_NATE_MEDIUM_RE = re.compile(r'<span class="medium">(.*?)</span>', re.S)
_ZUM_H2_RE = re.compile(r'<h2 class="title"[^>]*>(.*?)</h2>', re.S)
_ZUM_ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>', re.S)
_ZUM_MEDIA_RE = re.compile(r'<span class="media">(.*?)</span>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# 순위 변화 및 최초 관측 시각 추적 스냅샷
# { key: {"first_seen_at": str, "last_rank": int, "last_seen_at": str} }
_RANKING_HISTORY: dict[str, dict[str, Any]] = {}


def _reset_ranking_history() -> None:
    """테스트 및 세션 초기화용."""
    _RANKING_HISTORY.clear()


def _track_ranking_item(item_key: str, rank: int, now_iso: str | None = None) -> dict[str, Any]:
    """순위 스냅샷을 통해 신규 진입 여부, 순위 변화, 최초 관측 시각을 계산한다."""
    now_str = now_iso or datetime.now(UTC).isoformat()
    if item_key not in _RANKING_HISTORY:
        _RANKING_HISTORY[item_key] = {
            "first_seen_at": now_str,
            "last_rank": rank,
            "last_seen_at": now_str,
        }
        return {
            "first_seen_at": now_str,
            "is_new": True,
            "rank_change": None,
            "status": "new",
        }

    prev = _RANKING_HISTORY[item_key]
    first_seen_at = prev["first_seen_at"]
    last_rank = prev.get("last_rank")
    if last_rank is not None:
        diff = last_rank - rank  # 직전 5위 -> 현재 2위면 +3 (3계단 상승)
        status_str = f"+{diff}" if diff > 0 else str(diff)
        rank_change = diff
        is_new = False
    else:
        rank_change = None
        status_str = "new"
        is_new = True

    prev["last_rank"] = rank
    prev["last_seen_at"] = now_str
    return {
        "first_seen_at": first_seen_at,
        "is_new": is_new,
        "rank_change": rank_change,
        "status": status_str,
    }


def _extract_nate_published_at(medium_raw: str, url: str) -> str | None:
    """네이트 medium 태그(날짜) 또는 기사 URL에서 발표 시각을 추출한다."""
    m_date = re.search(
        r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?",
        medium_raw,
    )
    if m_date:
        try:
            year, month, day = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
            hour = int(m_date.group(4)) if m_date.group(4) else 0
            minute = int(m_date.group(5)) if m_date.group(5) else 0
            second = int(m_date.group(6)) if m_date.group(6) else 0
            return datetime(year, month, day, hour, minute, second, tzinfo=_KST).isoformat()
        except ValueError:
            pass

    m_url = re.search(r"/view/(\d{4})(\d{2})(\d{2})", url)
    if m_url:
        try:
            year, month, day = int(m_url.group(1)), int(m_url.group(2)), int(m_url.group(3))
            return datetime(year, month, day, 0, 0, 0, tzinfo=_KST).isoformat()
        except ValueError:
            pass
    return None


def _extract_zum_published_at(url: str, tail_raw: str = "") -> str | None:
    """줌 뉴스 링크 URL 또는 본문 주변에서 발표 시각을 추출한다."""
    m14 = re.search(r"(?:_|[^\d])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])([0-5]\d)([0-5]\d)", url)
    if m14:
        try:
            dt = datetime(
                int(m14.group(1)),
                int(m14.group(2)),
                int(m14.group(3)),
                int(m14.group(4)),
                int(m14.group(5)),
                int(m14.group(6)),
                tzinfo=_KST,
            )
            return dt.isoformat()
        except ValueError:
            pass

    m8 = re.search(r"(?:_|[^\d])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\b|[^\d])", url)
    if m8:
        try:
            dt = datetime(
                int(m8.group(1)),
                int(m8.group(2)),
                int(m8.group(3)),
                0,
                0,
                0,
                tzinfo=_KST,
            )
            return dt.isoformat()
        except ValueError:
            pass
    return None


def _decode_body(payload: bytes) -> str:
    for encoding in ("utf-8", "euc-kr"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _clean_text(value: str) -> str:
    text = _TAG_RE.sub(" ", value)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _absolute_url(value: str) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        url = f"https:{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return url


def _publisher_token(text: str) -> str:
    cleaned = _clean_text(text)
    return cleaned.split()[0] if cleaned else ""


def _parse_nate_ranking_html(
    text: str, *, limit: int, now_iso: str | None = None
) -> list[dict[str, Any]]:
    """`span.tit`/`h2.tit` 제목과 같은 행의 링크를 문서 순서(=랭킹 순서)로 뽑는다."""
    text = _strip_comments(text)
    items: list[dict[str, Any]] = []
    current_time_iso = now_iso or datetime.now(UTC).isoformat()
    for anchor_match in _NATE_ITEM_RE.finditer(text):
        rank_text, href, inner = anchor_match.groups()
        url = _absolute_url(href)
        if not url or "/view/" not in href:
            continue
        title_match = _NATE_TITLE_RE.search(inner)
        title = _clean_text(title_match.group(1)) if title_match else _clean_text(inner)
        if not title:
            continue
        tail = text[anchor_match.end() : anchor_match.end() + 600]
        publisher = ""
        medium_raw = ""
        medium_match = _NATE_MEDIUM_RE.search(tail)
        if medium_match:
            medium_raw = medium_match.group(1)
            publisher = _publisher_token(medium_raw)

        rank_val = int(rank_text)
        published_at = _extract_nate_published_at(medium_raw, url)
        tracking = _track_ranking_item(url or title, rank_val, now_iso=current_time_iso)
        first_seen_at = tracking["first_seen_at"]

        age_basis = "source_published_at" if published_at else ("first_seen_at" if first_seen_at else "unknown")

        items.append(
            {
                "title": title,
                "url": url,
                "source": "네이트 뉴스 랭킹",
                "publisher": publisher,
                "rank": rank_val,
                "source_published_at": published_at,
                "published_at": published_at,
                "first_seen_at": first_seen_at,
                "observed_at": current_time_iso,
                "age_basis": age_basis,
                "is_new": tracking["is_new"],
                "rank_change": tracking["rank_change"],
                "status": tracking["status"],
            }
        )
        if len(items) >= limit:
            break
    return items


def _parse_zum_news_html(
    text: str, *, limit: int, now_iso: str | None = None
) -> list[dict[str, Any]]:
    """`h2.title` 뉴스 제목과 감싸는 링크·바로 다음 매체명을 뽑는다."""
    text = _strip_comments(text)
    items: list[dict[str, Any]] = []
    current_time_iso = now_iso or datetime.now(UTC).isoformat()
    for h2_match in _ZUM_H2_RE.finditer(text):
        title = _clean_text(h2_match.group(1))
        if not title:
            continue
        prefix = text[: h2_match.start()]
        anchor_hrefs = _ZUM_ANCHOR_RE.findall(prefix)
        url = _absolute_url(anchor_hrefs[-1]) if anchor_hrefs else ""
        if not url:
            continue
        tail = text[h2_match.end() : h2_match.end() + 1200]
        publisher = ""
        medium_raw = ""
        media_match = _ZUM_MEDIA_RE.search(tail)
        if media_match:
            medium_raw = media_match.group(1)
            publisher = _publisher_token(medium_raw)

        rank_val = len(items) + 1
        published_at = _extract_zum_published_at(url, tail)
        tracking = _track_ranking_item(url or title, rank_val, now_iso=current_time_iso)
        first_seen_at = tracking["first_seen_at"]

        age_basis = "source_published_at" if published_at else ("first_seen_at" if first_seen_at else "unknown")

        items.append(
            {
                "title": title,
                "url": url,
                "source": "줌 뉴스",
                "publisher": publisher,
                "rank": rank_val,
                "source_published_at": published_at,
                "published_at": published_at,
                "first_seen_at": first_seen_at,
                "observed_at": current_time_iso,
                "age_basis": age_basis,
                "is_new": tracking["is_new"],
                "rank_change": tracking["rank_change"],
                "status": tracking["status"],
            }
        )
        if len(items) >= limit:
            break
    return items


def _normalize_title_key(title: str) -> str:
    return re.sub(r"[\W_]+", "", str(title or ""), flags=re.UNICODE).casefold()


def _dedupe_across_portals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in items:
        key = _normalize_title_key(item["title"])
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        deduped.append(item)
    return deduped


async def _get_parsed(
    session: httpx.AsyncClient,
    url: str,
    parser: Any,
    *,
    limit: int,
    retries: int = 1,
) -> list[dict[str, Any]]:
    """가져와 파싱하되, 빈 결과는 포털 일시 변형일 수 있어 한 번 재시도한다."""
    last: list[dict[str, Any]] = []
    for _ in range(retries + 1):
        response = await session.get(
            url,
            headers={"User-Agent": _BROWSER_USER_AGENT},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        last = parser(_decode_body(response.content), limit=limit)
        if last:
            return last
    return last


async def _fetch_nate_news_ranking(session: httpx.AsyncClient, *, limit: int) -> list[dict[str, Any]]:
    return await _get_parsed(session, NATE_NEWS_RANKING_URL, _parse_nate_ranking_html, limit=limit)


async def _fetch_zum_news(session: httpx.AsyncClient, *, limit: int) -> list[dict[str, Any]]:
    return await _get_parsed(session, ZUM_NEWS_RANKING_URL, _parse_zum_news_html, limit=limit)


async def _async_fetch_news_rankings(session: httpx.AsyncClient, limit: int = 30) -> list[dict[str, Any]]:
    """네이트 + 줌 뉴스 랭킹을 각 포털의 순서 그대로 합쳐 돌려준다.

    두 포털에 같은 제목이 올라온 사건은 첫 등장(네이트 우선) 하나로
    묶는다. 점수는 만들지 않고 순서만 보존한다.
    """
    nate_items = await _fetch_nate_news_ranking(session, limit=limit)
    zum_items = await _fetch_zum_news(session, limit=limit)
    return _dedupe_across_portals([*nate_items, *zum_items])
