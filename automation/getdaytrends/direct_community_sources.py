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
    # 베스트 승격 전 사건형 서사는 freeb·national·strange에 먼저 쌓인다. 소스 키를 게시판별로
    # 나누는 이유는 중복 제거·헬스 표시가 소스 단위로 돌기 때문이다.
    {
        "key": "bobae",
        "label": "보배드림 베스트",
        "url": "https://www.bobaedream.co.kr/list?code=best",
    },
    {
        "key": "bobae_freeb",
        "label": "보배드림 자유",
        "url": "https://www.bobaedream.co.kr/list?code=freeb",
    },
    {
        "key": "bobae_national",
        "label": "보배드림 국내",
        "url": "https://www.bobaedream.co.kr/list?code=national",
    },
    {
        "key": "bobae_strange",
        "label": "보배드림 신유머",
        "url": "https://www.bobaedream.co.kr/list?code=strange",
    },
    # 2026-08-06 소스 확대. 기존 네 곳이 전부 유머 게시판이라 사연·고민 소재가 얇았다.
    # robots를 각각 확인하고 통과한 곳만 붙였다(뽐뿌 Allow:/zboard/, 오늘의유머 Allow:/ +
    # Content-Signal ai-train=no).
    # 오늘의유머는 AI 학습 금지를 명시했다 — 우리는 목록을 읽어 사람에게 보여줄 뿐,
    # 어떤 모델도 학습시키지 않는다. 그 경계를 넘는 용도로 이 소스를 쓰지 않는다.
    #
    # 82cook은 2026-08-06에 IP 단위 443 연결 거부가 확인돼 직접 수집에서 뺐다.
    # robots는 허용이지만 요청 빈도로 서버가 끊는 구조라, 헤더 위장·자동화로 뚫지 않는다.
    # IssueLink 경유 표시는 그대로 둔다. 차단이 풀리면 파서(parse_82cook_free)는 재사용 가능하다.
    {
        "key": "ppomppu",
        "label": "뽐뿌 HOT",
        "url": "https://www.ppomppu.co.kr/hot.php",
    },
    {
        "key": "ppomppu_freeboard",
        "label": "뽐뿌 자유",
        "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard",
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

    # 보배드림 일반 게시판은 오늘이 아니면 "08/05"처럼 월/일만 찍는다(시각 없음 → 그날 00:00).
    month_day = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if month_day:
        published = datetime(
            local_now.year,
            int(month_day.group(1)),
            int(month_day.group(2)),
            0,
            0,
            tzinfo=_KST,
        )
        if published > local_now + timedelta(hours=12):
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


def parse_bobaedream_board(
    html: str,
    *,
    board_code: str = "best",
    source: str = "bobae",
    label: str = "보배드림",
    default_category: str = "보배드림",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """보배드림 목록 파서. best·freeb·national·strange가 같은 테이블 구조를 쓴다.

    링크의 code= 값만 게시판마다 다르므로 board_code로 걸러 소스 키를 분리한다.
    """
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    code_marker = f"code={board_code}"
    for position, row in enumerate(soup.select("tr")):
        link = None
        for candidate in row.select("a.bsubject"):
            href_raw = str(candidate.get("href") or "").replace("&amp;", "&")
            if code_marker in href_raw:
                link = candidate
                break
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]No=(\d+)", href)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        # title 속성에 잘리지 않은 제목이 있으면 그쪽을 우선한다.
        title = " ".join(str(link.get("title") or "").split()) or " ".join(
            link.get_text(" ", strip=True).split()
        )
        if not title or title.startswith("[공지]"):
            continue
        seen.add(post_id)
        time_node = row.select_one("td.date")
        published_label = " ".join(time_node.get_text(" ", strip=True).split()) if time_node else ""
        category_node = row.select_one("td.category")
        # 베스트 목록의 카테고리 글자는 "신유머/이.."처럼 잘려 나온다. title 속성에 전체 이름이 있다.
        category = ""
        if category_node is not None:
            category = " ".join(str(category_node.get("title") or "").split()) or " ".join(
                category_node.get_text(" ", strip=True).split()
            )
        items.append(
            _base_item(
                source=source,
                label=label,
                post_id=post_id,
                title=title,
                url=urljoin("https://www.bobaedream.co.kr", href),
                category=category or default_category,
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


def parse_bobaedream_best(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    return parse_bobaedream_board(
        html,
        board_code="best",
        source="bobae",
        label="보배드림 베스트",
        default_category="보배드림 베스트",
        now=now,
    )


def parse_bobaedream_freeb(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    return parse_bobaedream_board(
        html,
        board_code="freeb",
        source="bobae_freeb",
        label="보배드림 자유",
        default_category="보배드림 자유게시판",
        now=now,
    )


def parse_bobaedream_national(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    return parse_bobaedream_board(
        html,
        board_code="national",
        source="bobae_national",
        label="보배드림 국내",
        default_category="보배드림 국내이슈",
        now=now,
    )


def parse_bobaedream_strange(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    return parse_bobaedream_board(
        html,
        board_code="strange",
        source="bobae_strange",
        label="보배드림 신유머",
        default_category="보배드림 신유머/이슈",
        now=now,
    )


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
                source="82cook",
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


def parse_ppomppu_list(
    html: str,
    *,
    source: str = "ppomppu",
    label: str = "뽐뿌",
    default_category: str = "뽐뿌",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """뽐뿌 freeboard·hot.php 공통 파서.

    freeboard는 td.baseList-views/rec 클래스를 쓰고, hot.php는 td.board_date 세 칸
    (시각·추천-비추·조회)을 쓴다. 댓글은 freeboard에 없고 hot에는 span.list_comment2다.
    """
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, row in enumerate(soup.select("tr.baseList")):
        link = row.select_one("a.baseList-title")
        href = str(link.get("href") or "") if link else ""
        match = re.search(r"[?&]no=(\d+)", href, flags=re.IGNORECASE)
        if link is None or match is None or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        # hot.php 제목 옆에 붙은 댓글 숫자·아이콘 alt를 걷어낸다.
        title = re.sub(r"\s+\d+\s*$", "", title).strip()
        if not title:
            continue
        seen.add(post_id)

        published_label = ""
        for cell in row.select("td.baseList-space, td.board_date"):
            text = " ".join(cell.get_text(" ", strip=True).split())
            if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
                published_label = text[:5]
                break

        views_node = row.select_one("td.baseList-views")
        votes_node = row.select_one("td.baseList-rec")
        board_dates = row.select("td.board_date")
        if views_node is not None:
            views = _parse_count(views_node.get_text(" ", strip=True))
        elif board_dates:
            views = _parse_count(board_dates[-1].get_text(" ", strip=True))
        else:
            views = 0
        if votes_node is not None:
            votes = _parse_count(votes_node.get_text(" ", strip=True))
        elif len(board_dates) >= 2:
            # hot.php: "17 - 0" (추천 - 비추)
            votes = _parse_count(board_dates[1].get_text(" ", strip=True))
        else:
            votes = 0
        comment_node = row.select_one("span.list_comment2")
        comments = _parse_count(comment_node.get_text(" ", strip=True)) if comment_node else 0

        board_node = row.select_one("td.baseList-numb a")
        category = (
            " ".join(board_node.get_text(" ", strip=True).split()) if board_node else default_category
        ) or default_category

        items.append(
            _base_item(
                source=source,
                label=label,
                post_id=post_id,
                title=title,
                url=urljoin("https://www.ppomppu.co.kr/zboard/", href),
                category=category,
                published_label=published_label,
                age_minutes=_age_minutes(published_label, reference),
                views=views,
                votes=votes,
                comments=comments,
                position=position,
            )
        )
    return items


def parse_ppomppu_free(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """자유게시판 목록. 하위 호환 이름 — 새 코드는 source 키로 구분된 래퍼를 쓴다."""
    return parse_ppomppu_list(
        html,
        source="ppomppu_freeboard",
        label="뽐뿌 자유",
        default_category="뽐뿌 자유게시판",
        now=now,
    )


def parse_ppomppu_hot(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    return parse_ppomppu_list(
        html,
        source="ppomppu",
        label="뽐뿌 HOT",
        default_category="뽐뿌 HOT",
        now=now,
    )


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
    "bobae": parse_bobaedream_best,
    "bobae_freeb": parse_bobaedream_freeb,
    "bobae_national": parse_bobaedream_national,
    "bobae_strange": parse_bobaedream_strange,
    # 82cook은 직접 수집 목록에서 뺐지만 파서·키는 남겨 둔다(IssueLink·재개용).
    "82cook": parse_82cook_free,
    "ppomppu": parse_ppomppu_hot,
    "ppomppu_freeboard": parse_ppomppu_free,
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
