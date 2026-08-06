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
    # robots.txt가 `User-agent: * / Allow: /`로 전체 허용인 것을 2026-08-06에 확인하고 추가했다.
    # 자동차·시사 비중이 커서 기존 제외 필터(스포츠·정치·증시·실적·부동산)에 걸리는 글이 다른
    # 세 곳보다 많다 — 그건 필터가 처리하고, 여기서는 목록만 그대로 읽는다.
    {
        "key": "bobaedream",
        "label": "보배드림",
        "url": "https://www.bobaedream.co.kr/list?code=best",
    },
    # 2026-08-06 소스 확대. 기존 네 곳이 전부 유머 게시판이라 사연·고민 소재가 얇았다.
    # robots를 각각 확인하고 통과한 곳만 붙였다(뽐뿌 Allow:/zboard/, 82cook 특정 경로만
    # 금지, 오늘의유머 Allow:/ + Content-Signal ai-train=no).
    # 오늘의유머는 AI 학습 금지를 명시했다 — 우리는 목록을 읽어 사람에게 보여줄 뿐,
    # 어떤 모델도 학습시키지 않는다. 그 경계를 넘는 용도로 이 소스를 쓰지 않는다.
    {
        "key": "cook82",
        "label": "82cook",
        "url": "https://www.82cook.com/entiz/enti.php?bn=15",
    },
    {
        "key": "ppomppu",
        "label": "뽐뿌",
        "url": "https://www.ppomppu.co.kr/hot.php",
    },
    {
        "key": "todayhumor",
        "label": "오늘의유머",
        "url": "https://www.todayhumor.co.kr/board/list.php?table=bestofbest",
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


def parse_bobaedream_best(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr")):
        link = row.select_one('a.bsubject[href*="code=best"]')
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]No=(\d+)", href)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title:
            continue
        seen.add(post_id)
        time_node = row.select_one("td.date")
        published_label = " ".join(time_node.get_text(" ", strip=True).split()) if time_node else ""
        category_node = row.select_one("td.category")
        # 목록의 카테고리 글자는 "신유머/이.."처럼 잘려 나온다. title 속성에 전체 이름이 있다.
        category = ""
        if category_node is not None:
            category = " ".join(str(category_node.get("title") or "").split()) or " ".join(
                category_node.get_text(" ", strip=True).split()
            )
        items.append(
            _base_item(
                source="bobaedream",
                label="보배드림",
                post_id=post_id,
                title=title,
                url=urljoin("https://www.bobaedream.co.kr", href),
                category=category or "보배드림 베스트",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count((row.select_one("td.count") or row).get_text(" ", strip=True))
                if row.select_one("td.count")
                else 0,
                votes=_parse_count((row.select_one("td.recomm") or row).get_text(" ", strip=True))
                if row.select_one("td.recomm")
                else 0,
                comments=_parse_count(
                    (row.select_one("strong.totreply") or row).get_text(" ", strip=True)
                )
                if row.select_one("strong.totreply")
                else 0,
                position=position,
            )
        )
    return items


def parse_82cook_free(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr")):
        if "noticeList" in (row.get("class") or []):
            continue
        link = row.select_one('td.title > a[href*="read.php"]')
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]num=(\d+)", href)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title:
            continue
        seen.add(post_id)
        date_node = row.select_one("td.regdate")
        # 목록 텍스트는 "18:42:20"인데 title 속성에 "2026-08-06 18:42:20" 전체가 있다.
        stamp = " ".join(str(date_node.get("title") or "").split()) if date_node else ""
        published_label = stamp[-8:-3] if len(stamp) >= 16 else (
            " ".join(date_node.get_text(" ", strip=True).split())[:5] if date_node else ""
        )
        numbers = row.select("td.numbers")
        items.append(
            _base_item(
                source="cook82",
                label="82cook",
                post_id=post_id,
                title=title,
                url=urljoin("https://www.82cook.com/entiz/", href),
                category="82cook 자유게시판",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count(numbers[-1].get_text(" ", strip=True)) if numbers else 0,
                votes=0,
                comments=_parse_count((row.select_one("td.title em") or row).get_text(" ", strip=True))
                if row.select_one("td.title em")
                else 0,
                position=position,
            )
        )
    return items


def parse_ppomppu_free(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr.baseList")):
        link = row.select_one("a.baseList-title")
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]no=(\d+)", href)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title:
            continue
        seen.add(post_id)
        cells = row.select("td.baseList-space")
        published_label = ""
        for cell in cells:
            text = " ".join(cell.get_text(" ", strip=True).split())
            if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
                published_label = text[:5]
                break
        items.append(
            _base_item(
                source="ppomppu",
                label="뽐뿌",
                post_id=post_id,
                title=title,
                url=urljoin("https://www.ppomppu.co.kr/zboard/", href),
                category="뽐뿌 자유게시판",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count((row.select_one("td.baseList-views") or row).get_text(" ", strip=True))
                if row.select_one("td.baseList-views")
                else 0,
                votes=_parse_count((row.select_one("td.baseList-rec") or row).get_text(" ", strip=True))
                if row.select_one("td.baseList-rec")
                else 0,
                comments=0,
                position=position,
            )
        )
    return items


def parse_todayhumor_best(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr.view")):
        link = row.select_one('td.subject a[href*="view.php"]')
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]no=(\d+)", href)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        # 댓글 수는 제목 링크 밖의 별도 span에 있다("<a>제목</a><span> [9]</span>").
        comment_node = row.select_one("td.subject span.list_memo_count_span")
        if not title:
            continue
        seen.add(post_id)
        date_node = row.select_one("td.date")
        # "26/08/06 09:15" 형식 — 시각만 넘겨 오늘 기준으로 계산한다.
        stamp = " ".join(date_node.get_text(" ", strip=True).split()) if date_node else ""
        published_label = stamp.split(" ")[-1] if " " in stamp else ""
        items.append(
            _base_item(
                source="todayhumor",
                label="오늘의유머",
                post_id=post_id,
                title=title,
                url=urljoin("https://www.todayhumor.co.kr", href),
                category="오늘의유머 베오베",
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=_parse_count((row.select_one("td.hits") or row).get_text(" ", strip=True))
                if row.select_one("td.hits")
                else 0,
                votes=_parse_count((row.select_one("td.oknok") or row).get_text(" ", strip=True))
                if row.select_one("td.oknok")
                else 0,
                comments=_parse_count(comment_node.get_text(" ", strip=True)) if comment_node else 0,
                position=position,
            )
        )
    return items


_PARSERS = {
    "dogdrip": parse_dogdrip_latest,
    "theqoo": parse_theqoo_hot,
    "ruliweb": parse_ruliweb_best,
    "bobaedream": parse_bobaedream_best,
    "cook82": parse_82cook_free,
    "ppomppu": parse_ppomppu_free,
    "todayhumor": parse_todayhumor_best,
}


def parse_direct_community_source(
    source: str,
    html: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    parser = _PARSERS.get(source)
    return parser(html, now=now) if parser else []
