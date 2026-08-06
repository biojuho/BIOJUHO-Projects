"""Parsers for public, direct community listing pages.

Only listing metadata and publisher-original URLs are collected. Article bodies
are never copied, and a source parse failure is isolated from the other feeds.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


_KST = timezone(timedelta(hours=9))

DIRECT_COMMUNITY_SOURCES = (
    {
        "key": "dogdrip",
        "label": "개드립",
        "url": "https://www.dogdrip.net/dogdrip",
    },
    {
        "key": "theqoo",
        "label": "더쿠",
        "url": "https://theqoo.net/hot",
    },
    {
        "key": "ruliweb",
        "label": "루리웹",
        "url": "https://bbs.ruliweb.com/best/humor",
    },
)


def _parse_count(value: str) -> int:
    match = re.search(r"([\d,]+)", value.replace("\xa0", " "))
    return int(match.group(1).replace(",", "")) if match else 0


def _age_minutes(label: str, now: datetime) -> int | None:
    text = " ".join(label.split())
    relative = re.search(r"(\d+)\s*(분|시간|일)\s*전", text)
    if relative:
        amount = int(relative.group(1))
        return amount * {"분": 1, "시간": 60, "일": 1440}[relative.group(2)]

    local_now = now.astimezone(_KST)
    clock = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if clock:
        published = local_now.replace(
            hour=int(clock.group(1)), minute=int(clock.group(2)), second=0, microsecond=0
        )
        if published > local_now + timedelta(minutes=5):
            published -= timedelta(days=1)
        return max(0, round((local_now - published).total_seconds() / 60))

    dated = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if dated:
        published = datetime(
            local_now.year,
            int(dated.group(1)),
            int(dated.group(2)),
            int(dated.group(3)),
            int(dated.group(4)),
            tzinfo=_KST,
        )
        if published > local_now + timedelta(days=1):
            published = published.replace(year=local_now.year - 1)
        return max(0, round((local_now - published).total_seconds() / 60))
    return None


def _base_item(
    *,
    source: str,
    label: str,
    post_id: str,
    title: str,
    url: str,
    category: str,
    published_label: str,
    age_minutes: int | None,
    views: int,
    votes: int,
    comments: int,
    position: int,
) -> dict[str, Any]:
    return {
        "id": post_id,
        "title": title,
        "category": category,
        "community_source": source,
        "community_label": label,
        "source_url": url,
        "link_kind": "publisher_original",
        "published_label": published_label,
        "age_minutes": age_minutes,
        "views": views,
        "votes": votes,
        "comments": comments,
        "source_position": position,
        "signal_source": "직접 목록",
    }


def parse_dogdrip_latest(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, link in enumerate(soup.select("li.webzine a.title-link[data-document-srl]")):
        post_id = str(link.get("data-document-srl") or "").strip()
        title = " ".join(link.get_text(" ", strip=True).split())
        row = link.find_parent("li")
        if not post_id or not title or row is None or post_id in seen:
            continue
        seen.add(post_id)
        comment_node = link.find_next_sibling("span")
        time_node = row.select_one(".list-meta .text-muted")
        published_label = " ".join(time_node.get_text(" ", strip=True).split()) if time_node else ""
        vote_values = [
            _parse_count(node.get_text(" ", strip=True))
            for node in row.select(".list-meta span.text-primary")
            if re.search(r"\d", node.get_text(" ", strip=True))
        ]
        items.append(
            _base_item(
                source="dogdrip",
                label="개드립",
                post_id=post_id,
                title=title,
                url=urljoin("https://www.dogdrip.net", str(link.get("href") or "")),
                category="개드립",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=0,
                votes=max(vote_values, default=0),
                comments=_parse_count(comment_node.get_text(" ", strip=True)) if comment_node else 0,
                position=position,
            )
        )
    return items


def parse_theqoo_hot(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr")):
        if "notice" in (row.get("class") or []):
            continue
        link = row.select_one('td.title > a[href^="/hot/"]:not(.replyNum)')
        match = re.fullmatch(r"/hot/(\d+)", str(link.get("href") or "").split("?", 1)[0]) if link else None
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title:
            continue
        seen.add(post_id)
        time_node = row.select_one("td.time")
        published_label = " ".join(time_node.get_text(" ", strip=True).split()) if time_node else ""
        items.append(
            _base_item(
                source="theqoo",
                label="더쿠",
                post_id=post_id,
                title=title,
                url=urljoin("https://theqoo.net", str(link.get("href") or "")),
                category=" ".join((row.select_one("td.cate") or row).get_text(" ", strip=True).split())
                if row.select_one("td.cate")
                else "더쿠 HOT",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count((row.select_one("td.m_no") or row).get_text(" ", strip=True))
                if row.select_one("td.m_no")
                else 0,
                votes=0,
                comments=_parse_count(
                    (row.select_one("a.replyNum") or row).get_text(" ", strip=True)
                )
                if row.select_one("a.replyNum")
                else 0,
                position=position,
            )
        )
    return items


def parse_ruliweb_best(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr.table_body")):
        link = row.select_one('a.subject_link[href*="/read/"]')
        match = re.search(r"/read/(\d+)", str(link.get("href") or "")) if link else None
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title_node = link.select_one("strong.text_over")
        title = " ".join((title_node or link).get_text(" ", strip=True).split())
        title = re.sub(r"\s*\([\d,]+\)\s*$", "", title).strip()
        if not title:
            continue
        seen.add(post_id)
        time_node = row.select_one("td.time")
        published_label = " ".join(time_node.get_text(" ", strip=True).split()) if time_node else ""
        items.append(
            _base_item(
                source="ruliweb",
                label="루리웹",
                post_id=post_id,
                title=title,
                url=urljoin("https://bbs.ruliweb.com", str(link.get("href") or "")),
                category="루리웹 베스트",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count((row.select_one("td.hit") or row).get_text(" ", strip=True))
                if row.select_one("td.hit")
                else 0,
                votes=_parse_count((row.select_one("td.recomd") or row).get_text(" ", strip=True))
                if row.select_one("td.recomd")
                else 0,
                comments=_parse_count(
                    (link.select_one("span.num_reply") or link).get_text(" ", strip=True)
                )
                if link.select_one("span.num_reply")
                else 0,
                position=position,
            )
        )
    return items


_PARSERS = {
    "dogdrip": parse_dogdrip_latest,
    "theqoo": parse_theqoo_hot,
    "ruliweb": parse_ruliweb_best,
}


def parse_direct_community_source(
    source: str,
    html: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    parser = _PARSERS.get(source)
    return parser(html, now=now) if parser else []
