"""네이트·줌 뉴스 랭킹 수집기.

제목 전문·링크·소스명만 가져온다. 뉴스 본문은 긁지 않는다(핸드오프 0068 금지사항).
네이트는 euc-kr로 내려올 수 있어 utf-8 → euc-kr 디코딩 폴백을 둔다.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)

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


def _parse_nate_ranking_html(text: str, *, limit: int) -> list[dict[str, Any]]:
    """`span.tit`/`h2.tit` 제목과 같은 행의 링크를 문서 순서(=랭킹 순서)로 뽑는다."""
    text = _strip_comments(text)
    items: list[dict[str, Any]] = []
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
        medium_match = _NATE_MEDIUM_RE.search(tail)
        if medium_match:
            publisher = _publisher_token(medium_match.group(1))
        items.append(
            {
                "title": title,
                "url": url,
                "source": "네이트 뉴스 랭킹",
                "publisher": publisher,
                "rank": int(rank_text),
            }
        )
        if len(items) >= limit:
            break
    return items


def _parse_zum_news_html(text: str, *, limit: int) -> list[dict[str, Any]]:
    """`h2.title` 뉴스 제목과 감싸는 링크·바로 다음 매체명을 뽑는다."""
    text = _strip_comments(text)
    items: list[dict[str, Any]] = []
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
        media_match = _ZUM_MEDIA_RE.search(tail)
        if media_match:
            publisher = _publisher_token(media_match.group(1))
        items.append(
            {
                "title": title,
                "url": url,
                "source": "줌 뉴스",
                "publisher": publisher,
                "rank": len(items) + 1,
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
