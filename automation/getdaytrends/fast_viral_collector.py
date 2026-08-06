"""Early viral-material detector using direct community velocity signals."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

try:
    from .content_filters import excluded_topic_reason
    from .kernel_screen import screen_material, sort_by_kernel
    from .og_enrich import OgEnrichmentReport, fetch_og_descriptions
    from .source_backoff import SourceBackoff
    from .direct_community_sources import DIRECT_COMMUNITY_SOURCES, parse_direct_community_source
    from .exposure_observation_tracker import ExposureObservationTracker
    from .lead_time_tracker import LeadTimeTracker
except ImportError:
    from content_filters import excluded_topic_reason
    from kernel_screen import screen_material, sort_by_kernel
    from og_enrich import OgEnrichmentReport, fetch_og_descriptions
    from source_backoff import SourceBackoff
    from direct_community_sources import DIRECT_COMMUNITY_SOURCES, parse_direct_community_source
    from exposure_observation_tracker import ExposureObservationTracker
    from lead_time_tracker import LeadTimeTracker

if TYPE_CHECKING:
    from pathlib import Path

FMKOREA_HUMOR_URL = "https://www.fmkorea.com/humor?category=486622"
ISSUELINK_URL = "https://www.issuelink.co.kr/"
_KST = timezone(timedelta(hours=9))

# 화면에서 애그리게이터(IssueLink) 경유 항목에 내어 주는 비율.
#
# 올릴수록 커뮤니티 종류가 늘고(클리앙·인벤·뽐뿌·SLR·82cook처럼 직접 수집하지 않는 곳),
# 내릴수록 지표가 튼튼한 항목이 늘어난다 — 애그리게이터 항목은 조회·추천 수치가 없고
# 댓글 수와 교차 노출만으로 점수를 매기기 때문이다. 0.5는 그 사이의 기본값이다.
# `.env`의 GETDAYTRENDS_AGGREGATOR_SHARE로 조정한다.
_AGGREGATOR_SHARE_DEFAULT = 0.5
_AGGREGATOR_SHARE_MIN = 0.1
_AGGREGATOR_SHARE_MAX = 0.9


def _aggregator_share() -> float:
    raw = os.getenv("GETDAYTRENDS_AGGREGATOR_SHARE")
    if raw is None or not raw.strip():
        return _AGGREGATOR_SHARE_DEFAULT
    try:
        value = float(raw.strip())
    except ValueError:
        return _AGGREGATOR_SHARE_DEFAULT
    # 0이나 1을 그대로 받으면 한쪽 신호가 통째로 사라진다. 양끝을 남겨 둔다.
    return min(_AGGREGATOR_SHARE_MAX, max(_AGGREGATOR_SHARE_MIN, value))


# 직접 목록에서 후보로 받아들일 나이 상한과 최소 반응.
#
# 2026-08-06까지 상한이 45분이었다. 조기 탐지에는 맞지만, 그 결과 화면에는 조회 0·댓글 몇 개인
# "아직 아무도 안 본 글"만 올라왔다. X에 올릴 소재를 고르는 자리에서는 쓸 게 없다는 뜻이다.
# 신속성은 "뜨기 시작한 걸 남보다 먼저"이지 "아무도 안 본 걸 먼저"가 아니다 — 반응이 0이면
# 뜰 글인지 아닌지 판단할 근거 자체가 없다.
# 그래서 상한을 넓혀 반응이 쌓일 시간을 주되, 최소 반응을 통과한 것만 후보로 삼는다.
_DIRECT_MAX_AGE_DEFAULT = 360  # 6시간
_DIRECT_MIN_VIEWS_DEFAULT = 300
_DIRECT_MIN_COMMENTS_DEFAULT = 5


def _direct_max_age_minutes() -> int:
    raw = os.getenv("GETDAYTRENDS_DIRECT_MAX_AGE_MINUTES")
    try:
        return max(10, int((raw or "").strip())) if raw and raw.strip() else _DIRECT_MAX_AGE_DEFAULT
    except ValueError:
        return _DIRECT_MAX_AGE_DEFAULT


def has_min_traction(item: dict[str, Any]) -> bool:
    """반응이 시작된 글인가. 조회·댓글·추천 중 하나만 넘으면 통과한다.

    소스마다 노출하는 지표가 다르다 — 개드립은 조회를 안 주고, 뽐뿌는 댓글을 안 준다.
    셋 다 요구하면 소스별로 편식하게 되므로 하나라도 넘으면 받는다.
    """
    views = int(item.get("views") or 0)
    comments = int(item.get("comments") or 0)
    votes = int(item.get("votes") or 0)
    return views >= _DIRECT_MIN_VIEWS_DEFAULT or comments >= _DIRECT_MIN_COMMENTS_DEFAULT or votes >= 10


def passes_spread_gate(item: dict[str, Any], *, score: int, live_axis: bool) -> bool:
    """확산이 붙기 시작했는가. 사는 축 소재는 이 게이트를 면제받는다.

    사는 축(가해자 명확·낙차)은 X에서 판정이 붙는 소재라 조회가 늦게 온다. 예전에는
    임계만 낮춰(55→35) 통과시켰는데, 35점도 확산을 요구하는 숫자라 의도가 절반만
    구현돼 있었다 — 2026-08-07 새벽 실측에서 사는 축 6건 중 3건이 여기서 떨어졌고
    그중 하나는 통과선과 1점 차였다(34점, 군 부대 절도 고발).

    게다가 배점 40점을 차지하는 engagement는 댓글·추천으로만 매겨지는데 뽐뿌
    자유게시판은 댓글을 아예 주지 않는다. 그래서 조회 1,887인 글이 30점에 묶였다.
    `has_min_traction`은 이 편식을 이미 알고 하나만 넘으면 받아 주는데, 정작 점수는
    그대로 벌하고 있었다. 소스가 무엇을 노출하느냐가 커널 판정을 이겨서는 안 된다.

    나이·트랙션·브랜드 세이프티는 이 함수 앞의 게이트가 이미 지킨다. 여기서 푸는 것은
    확산 하나뿐이고, 정렬은 여전히 점수 순이라 구제된 소재는 아래에 붙는다.
    """
    if live_axis:
        return True
    views = int(item.get("views") or 0)
    if views > 0:
        return score >= 55 and views >= 80
    return score >= 45 and int(item.get("comments") or 0) + int(item.get("votes") or 0) >= 5


def aggregator_quota(limit: int, *, any_direct_ok: bool) -> int:
    """이번 화면에서 애그리게이터 경유 항목에 줄 자리 수."""
    if limit <= 0:
        return 0
    if not any_direct_ok:
        # 직접 목록이 전부 죽었으면 애그리게이터가 화면을 지킨다.
        return limit
    return max(1, min(limit - 1, round(limit * _aggregator_share())))
_COMMUNITY_EXPOSURE_SCORE_VERSION = "community-exposure-v2"
_BLOCKED_TITLE_MARKERS = (
    "ㅇㅎ",
    "ㅎㅂ",
    "후방",
    "19금",
    "야짤",
    "비키니",
    "ㅊㅈ",
    "유부녀 눈나",
    "노출녀",
    # 2026-08-06: 직접 소스를 넷으로 늘리자 성인성·화장실 유머가 화면에 올라왔다.
    # X에 올릴 소재를 고르는 자리라 여기서 끊는다. 단어 하나로 판단할 수 있는 것만 둔다.
    "69자세",
    "첫경험",
    "성관계",
    "섹스",
    "야동",
    "자위",
    "성인용품",
    "노브라",
    "몸매 甲",
    "가슴 성형",
    "성접대",
    "성상납",
    "유흥업소",
    "룸살롱",
)

# 단어 하나로는 못 거르는 것들. "똥손"·"똥차"·"오줌소태 병원"까지 걸리면 필터가 무뎌지므로
# 배설 소재로 읽히는 문맥일 때만 막는다.
_BLOCKED_TITLE_PATTERNS = (
    re.compile(r"똥\s*(?:을|싸|싼|쌌|닦|묻|치우|밟)"),
    re.compile(r"(?:대변|소변|오줌)\s*(?:을|보|싸|묻|테러)"),
    re.compile(r"방귀\s*(?:뀌|끼|냄새|테러)"),
    re.compile(r"(?:전립선|치질|항문)\s*(?:염|수술|치료|검사)"),
)
_COMMUNITY_LABELS = {
    "82cook": "82cook",
    "bobae": "보배드림 베스트",
    "bobae_freeb": "보배드림 자유",
    "bobae_national": "보배드림 국내",
    "bobae_strange": "보배드림 신유머",
    "clien": "클리앙",
    "dogdrip": "개드립",
    "etoland": "이토랜드",
    "fmkorea": "FMKorea",
    "humoruniv": "웃긴대학",
    "instiz": "인스티즈",
    "inven": "인벤",
    "mlbpark": "MLB파크",
    "ppomppu": "뽐뿌 HOT",
    "ppomppu_freeboard": "뽐뿌 자유",
    "ruliweb": "루리웹",
    "slr": "SLR클럽",
    "theqoo": "더쿠",
    "todayhumor": "오늘의유머",
    "ygosu": "와이고수",
}


def _parse_count(value: str) -> int:
    text = value.strip().replace(",", "")
    if not text:
        return 0
    match = re.search(r"([\d.]+)\s*(백만|만|천|k|m)?", text, flags=re.IGNORECASE)
    if not match:
        return 0
    number = float(match.group(1))
    multiplier = {
        "천": 1_000,
        "만": 10_000,
        "백만": 1_000_000,
        "k": 1_000,
        "m": 1_000_000,
    }.get((match.group(2) or "").casefold(), 1)
    return int(number * multiplier)


def _post_age_minutes(value: str, now: datetime) -> int | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not match:
        return None
    local_now = now.astimezone(_KST)
    published = local_now.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
    if published > local_now + timedelta(minutes=5):
        published -= timedelta(days=1)
    return max(0, round((local_now - published).total_seconds() / 60))


def _looks_blocked(response: Any) -> bool:
    """사이트가 자동 접근을 거부한 응답인지 판별한다.

    실패를 뭉뚱그리면 "고치면 되는 파싱 버그"로 보인다. 차단은 성격이 다르다 —
    우리가 물러서야 하는 쪽이라 화면에도 그렇게 적어야 한다.
    """
    status = getattr(response, "status_code", 0)
    if status in {401, 403, 429, 430, 451}:
        return True
    try:
        head = (response.text or "")[:2000]
    except Exception:
        return False
    return any(marker in head for marker in ("보안 시스템", "Just a moment", "cf-browser-verification"))


def parse_fmkorea_latest(html: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    reference = now or datetime.now(UTC)
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    rows = soup.select("table.bd_lst tbody tr") or soup.select("table.bd_lst tr")
    for row in rows:
        if "notice" in (row.get("class") or []):
            continue
        cells = row.select("td")
        title_link = row.select_one("td.title > a[href]")
        if len(cells) < 6 or title_link is None:
            continue
        href = str(title_link.get("href") or "")
        post_id_match = re.search(r"/(\d+)(?:\?.*)?$", href)
        title = " ".join(title_link.get_text(" ", strip=True).split())
        if not post_id_match or not title:
            continue
        reply = row.select_one("a.replyNum")
        items.append(
            {
                "id": post_id_match.group(1),
                "title": title,
                "category": " ".join(cells[0].get_text(" ", strip=True).split()),
                "source_url": urljoin("https://www.fmkorea.com", href),
                "published_label": cells[3].get_text(" ", strip=True),
                "age_minutes": _post_age_minutes(cells[3].get_text(" ", strip=True), reference),
                "views": _parse_count(cells[-2].get_text(" ", strip=True)),
                "votes": _parse_count(cells[-1].get_text(" ", strip=True)),
                "comments": _parse_count(reply.get_text(" ", strip=True)) if reply else 0,
            }
        )
    return items


def parse_issuelink_fmkorea_ids(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    ids: set[str] = set()
    for link in soup.select('a[href*="/community/go/fmkorea/"]'):
        match = re.search(r"/community/go/fmkorea/(\d+)", str(link.get("href") or ""))
        if match:
            ids.add(match.group(1))
    return ids


def parse_issuelink_fmkorea_items(html: str) -> list[dict[str, Any]]:
    """Extract unique FMKorea originals already visible on IssueLink.

    These records are a transparent availability fallback only. They must not be
    described as pre-aggregator discoveries because IssueLink already surfaced
    them.
    """
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/community/go/fmkorea/"]'):
        match = re.search(r"/community/go/fmkorea/(\d+)", str(link.get("href") or ""))
        if not match or match.group(1) in seen:
            continue
        post_id = match.group(1)
        title = " ".join(link.get_text(" ", strip=True).split())
        comments_match = re.search(r"\[(\d[\d,]*)\]\s*$", title)
        comments = _parse_count(comments_match.group(1)) if comments_match else 0
        title = re.sub(r"\s*\[\d[\d,]*\]\s*$", "", title).strip()
        if not title:
            continue
        seen.add(post_id)
        items.append(
            {
                "id": post_id,
                "title": title,
                "category": "IssueLink 백업",
                "source_url": f"https://www.fmkorea.com/{post_id}",
                "published_label": "",
                "age_minutes": None,
                "views": 0,
                "votes": 0,
                "comments": comments,
            }
        )
    return items


def parse_issuelink_community_items(html: str) -> list[dict[str, Any]]:
    """Extract unique community entries and their IssueLink redirect URLs."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, link in enumerate(soup.select('a[href*="/community/go/"]')):
        href = urljoin(ISSUELINK_URL, str(link.get("href") or ""))
        match = re.search(r"/community/go/([a-zA-Z0-9_-]+)/([0-9]+)", href)
        if not match:
            continue
        community_source, post_id = match.groups()
        key = f"{community_source}:{post_id}"
        if key in seen:
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        comments_match = re.search(r"\[(\d[\d,]*)\]\s*$", title)
        comments = _parse_count(comments_match.group(1)) if comments_match else 0
        title = re.sub(r"\s*\[\d[\d,]*\]\s*$", "", title).strip()
        if not title:
            continue
        seen.add(key)
        source_url = f"https://www.fmkorea.com/{post_id}" if community_source == "fmkorea" else href
        items.append(
            {
                "id": post_id,
                "title": title,
                "category": "IssueLink 집계 확인",
                "community_source": community_source,
                "community_label": _COMMUNITY_LABELS.get(community_source, community_source),
                "source_url": source_url,
                "aggregator_url": href,
                "link_kind": "publisher_original" if community_source == "fmkorea" else "redirect_pending",
                "published_label": "",
                "age_minutes": None,
                "views": 0,
                "votes": 0,
                "comments": comments,
                "source_position": position,
            }
        )
    return items


def _select_diverse_community_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        buckets.setdefault(item["community_source"], []).append(item)
    for bucket in buckets.values():
        bucket.sort(
            key=lambda item: (item.get("x_exposure_score", 0), item["comments"], -item["source_position"]),
            reverse=True,
        )
    source_order = sorted(
        buckets,
        key=lambda source: (
            buckets[source][0].get("x_exposure_score", 0),
            buckets[source][0]["comments"],
            -buckets[source][0]["source_position"],
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    while source_order and len(selected) < limit:
        remaining: list[str] = []
        for source in source_order:
            if buckets[source] and len(selected) < limit:
                selected.append(buckets[source].pop(0))
            if buckets[source]:
                remaining.append(source)
        source_order = remaining
    selected.sort(
        key=lambda item: (item.get("x_exposure_score", 0), item["comments"], -item["source_position"]),
        reverse=True,
    )
    return selected


_GENERIC_COMMUNITY_TOKENS = {
    "근황",
    "오늘",
    "현재",
    "현시각",
    "단독",
    "후기",
    "논란",
    "충격",
    "공개",
    "영상",
}
_VIRAL_EVENT_MARKERS = (
    "단독",
    "속보",
    "사고",
    "사망",
    "발견",
    "중단",
    "압수수색",
    "논란",
    "신제품",
    "공개",
    "목격담",
)


def _community_title_tokens(title: str) -> set[str]:
    cleaned = re.sub(r"\.(?:jpg|jpeg|png|gif|mp4)\b", " ", title.casefold())
    return {
        token
        for token in re.findall(r"[0-9a-z가-힣]{2,}", cleaned)
        if token not in _GENERIC_COMMUNITY_TOKENS
    }


def _community_titles_match(left: str, right: str) -> bool:
    left_key = re.sub(r"[\W_]+", "", left, flags=re.UNICODE).casefold()
    right_key = re.sub(r"[\W_]+", "", right, flags=re.UNICODE).casefold()
    if min(len(left_key), len(right_key)) >= 10 and (left_key in right_key or right_key in left_key):
        return True
    left_tokens = _community_title_tokens(left)
    right_tokens = _community_title_tokens(right)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap / len(left_tokens | right_tokens) >= 0.5


def _annotate_community_clusters(items: list[dict[str, Any]]) -> None:
    clusters: list[list[dict[str, Any]]] = []
    for item in items:
        cluster = next(
            (group for group in clusters if _community_titles_match(item["title"], group[0]["title"])),
            None,
        )
        if cluster is None:
            clusters.append([item])
        else:
            cluster.append(item)
    for cluster_id, cluster in enumerate(clusters, start=1):
        sources = sorted({str(item["community_source"]) for item in cluster})
        representative_tokens = sorted(_community_title_tokens(cluster[0]["title"]))
        representative = " ".join(representative_tokens) or re.sub(
            r"[\W_]+", "", cluster[0]["title"], flags=re.UNICODE
        ).casefold()
        cluster_key = hashlib.sha256(representative.encode("utf-8")).hexdigest()[:16]
        for item in cluster:
            item["community_cluster_id"] = cluster_id
            item["community_cluster_key"] = cluster_key
            item["community_mentions"] = len(cluster)
            item["cross_community_source_count"] = len(sources)
            item["cross_community_sources"] = sources


def _community_x_exposure_assessment(
    item: dict[str, Any],
    observation: dict[str, Any] | None = None,
) -> tuple[int, dict[str, int], list[str], str, float]:
    comments = max(0, int(item.get("comments") or 0))
    source_count = max(1, int(item.get("cross_community_source_count") or 1))
    title = str(item.get("title") or "")
    engagement = min(30, round(math.log10(comments + 1) * 10))
    cross_community = min(25, max(0, source_count - 1) * 13)
    event_signal = 15 if any(marker in title.casefold() for marker in _VIRAL_EVENT_MARKERS) else 0
    media_signal = 5 if re.search(r"\.(?:jpg|jpeg|png|gif|mp4)\b", title, flags=re.IGNORECASE) else 0
    compact_length = len(re.sub(r"\s+", "", title))
    topic_clarity = 10 if 10 <= compact_length <= 70 else 5
    observed = observation or {}
    comment_growth = max(0, int(observed.get("comment_growth") or 0))
    observed_growth = min(
        15,
        max(0, int(observed.get("new_sources") or 0)) * 5
        + max(0, int(observed.get("new_mentions") or 0)) * 2
        + min(5, round(math.log10(comment_growth + 1) * 3)),
    )
    breakdown = {
        "community_engagement": engagement,
        "cross_community": cross_community,
        "event_signal": event_signal,
        "media_signal": media_signal,
        "topic_clarity": topic_clarity,
        "observed_growth": observed_growth,
    }
    reasons = [f"댓글 {comments:,}개", f"커뮤니티 {source_count}곳 교차"]
    if event_signal:
        reasons.append("사건성 원문 제목")
    if media_signal:
        reasons.append("원문 미디어 포함")
    if observed.get("previous_observed_at"):
        reasons.append(
            "직전 관측 대비 "
            f"새 출처 +{int(observed.get('new_sources') or 0)} · "
            f"새 언급 +{int(observed.get('new_mentions') or 0)} · "
            f"댓글 +{comment_growth}"
        )
        confidence = "high" if source_count >= 2 else "medium"
    else:
        reasons.append("첫 관측 · 확산 증가량은 다음 갱신부터 계산")
        confidence = "medium" if source_count >= 2 else "low"
    coverage = {"high": 1.0, "medium": 0.92, "low": 0.82}[confidence]
    return min(100, round(sum(breakdown.values()) * coverage)), breakdown, reasons, confidence, coverage


async def _resolve_community_origins(session: httpx.AsyncClient, items: list[dict[str, Any]]) -> int:
    """Resolve only IssueLink's redirect header; do not scrape destination sites."""
    semaphore = asyncio.Semaphore(6)

    async def resolve(item: dict[str, Any]) -> bool:
        if item["link_kind"] == "publisher_original":
            return True
        try:
            async with semaphore:
                response = await session.head(
                    item["aggregator_url"],
                    follow_redirects=False,
                    timeout=httpx.Timeout(7.0, connect=3.0),
                )
            location = str(response.headers.get("location") or "").strip()
            parsed = urlparse(location)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold().endswith("issuelink.co.kr"):
                item["link_kind"] = "aggregator_redirect"
                return False
            item["source_url"] = location
            item["link_kind"] = "publisher_original"
            return True
        except httpx.HTTPError:
            item["link_kind"] = "aggregator_redirect"
            return False

    return sum(await asyncio.gather(*(resolve(item) for item in items)))


def _is_brand_safe_title(title: str) -> bool:
    normalized = title.casefold()
    if len(re.sub(r"\W", "", title)) < 6:
        return False
    if any(marker.casefold() in normalized for marker in _BLOCKED_TITLE_MARKERS):
        return False
    return not any(pattern.search(normalized) for pattern in _BLOCKED_TITLE_PATTERNS)


def _velocity_score(
    *,
    age_minutes: int,
    views: int,
    comments: int,
    votes: int,
    delta_views_per_minute: float,
    before_issuelink: bool,
) -> tuple[int, float]:
    lifetime_rate = views / max(age_minutes, 1)
    effective_rate = max(lifetime_rate, delta_views_per_minute)
    velocity_points = min(35, round(math.log10(effective_rate + 1) * 14))
    # 나이 상한을 360분으로 넓혔는데 신선도는 25분에서 0이 되고 있었다 —
    # 반응이 쌓일 시간을 준 글은 이 배점을 통째로 못 받았다. 상한에 맞춰 완만하게 감쇠한다.
    freshness_points = max(0, round(15 * (1 - min(age_minutes, 360) / 360)))
    # 댓글+추천 10개면 만점이라 댓글 500개와 10개가 같은 점수였다. 커뮤니티에서 댓글은
    # 추천보다 강한 신호이므로 가중치를 주고, 포화를 풀어 반응이 실제로 순위를 만들게 한다.
    engagement_points = min(40, round(math.log10(comments * 3 + votes + 1) * 16))
    # IssueLink에 아직 없다고 가산점을 주면 인과가 거꾸로다 — 잘 퍼지는 글일수록 이미 거기 있다.
    early_points = 5 if before_issuelink else 0
    return min(100, velocity_points + freshness_points + engagement_points + early_points), effective_rate


def _direct_signal_score(
    *,
    age_minutes: int,
    views: int,
    comments: int,
    votes: int,
    delta_views_per_minute: float,
    before_issuelink: bool,
) -> tuple[int, float | None]:
    if views > 0:
        return _velocity_score(
            age_minutes=age_minutes,
            views=views,
            comments=comments,
            votes=votes,
            delta_views_per_minute=delta_views_per_minute,
            before_issuelink=before_issuelink,
        )
    # 조회를 제공하지 않는 소스(개드립)용 경로. 여기도 35분 절벽을 완만한 감쇠로 바꾼다 —
    # 댓글+추천 177개를 요구하던 통과선 때문에 개드립은 구조적으로 화면에 못 올라왔다.
    freshness_points = max(0, round(20 * (1 - min(age_minutes, 360) / 360)))
    engagement_points = min(55, round(math.log10(comments * 3 + votes + 1) * 22))
    early_points = 5 if before_issuelink else 0
    return min(100, freshness_points + engagement_points + early_points), None


def _snapshot_item_key(item: dict[str, Any]) -> str:
    return f"{str(item.get('community_source') or 'fmkorea').casefold()}:{item.get('id')}"


async def _apply_og_second_pass(
    items: list[dict[str, Any]],
    *,
    source_backoff: SourceBackoff,
    fetcher: Any | None = None,
) -> dict[str, object]:
    """Apply OG only to final candidates whose title has no decisive signal.

    Descriptions live only long enough to call ``screen_material``. They are
    removed from the transient report before this function returns and are
    never attached to an item or snapshot.
    """
    candidates: list[tuple[dict[str, Any], str]] = []
    source_keys: dict[str, str] = {}
    for item in items:
        screen = item.get("kernel_screen")
        if not isinstance(screen, dict):
            screen = screen_material(item.get("title", ""), community_label=item.get("community_label"))
            item["kernel_screen"] = screen
        if screen.get("axis") not in {"dead_flat", "unknown"}:
            continue
        if item.get("link_kind") != "publisher_original":
            continue
        url = str(item.get("source_url") or "").strip()
        if not url:
            continue
        candidates.append((item, url))
        source_keys[url] = str(item.get("community_source") or "unknown")

    if not candidates:
        return OgEnrichmentReport().public_summary()

    fetch = fetcher or fetch_og_descriptions
    report = await fetch(
        [url for _, url in candidates],
        source_keys=source_keys,
        source_backoff=source_backoff,
    )
    for item, url in candidates:
        description = report.descriptions.get(url)
        if not description:
            continue
        item["kernel_screen"] = screen_material(
            item.get("title", ""),
            community_label=item.get("community_label"),
            summary=description,
        )

    public_summary = report.public_summary()
    report.descriptions.clear()
    return public_summary


class FastViralCollector:
    """Poll direct community listings and rank brand-safe early movers."""

    def __init__(self, snapshot_path: Path):
        self.snapshot_path = snapshot_path
        self.lead_tracker = LeadTimeTracker(snapshot_path.with_name("viral_lead_times.json"))
        self.exposure_tracker = ExposureObservationTracker(
            snapshot_path.with_name("community_exposure_observations.json")
        )
        self._refresh_lock = asyncio.Lock()
        self._last_attempt_at: datetime | None = None
        # 차단당한 소스를 5분마다 계속 두드리면 상대에게도 우리에게도 손해다.
        self._backoff = SourceBackoff()
        self._snapshot: dict[str, Any] = {
            "available": False,
            "items": [],
            "refreshed_at": None,
            "source_health": {"fmkorea_direct": False, "issuelink_confirmation": False},
            "errors": [],
        }

    def snapshot(self) -> dict[str, Any]:
        return dict(self._snapshot)

    def _load_previous(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def _save_current(self, polled_at: datetime, items: list[dict[str, Any]]) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "polled_at": polled_at.isoformat(),
            "items": {
                _snapshot_item_key(item): {"views": item["views"], "comments": item["comments"]}
                for item in items
            },
        }
        temp_path = self.snapshot_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.snapshot_path)

    async def refresh(self, *, limit: int = 12) -> dict[str, Any]:
        limit = min(30, max(5, int(limit)))
        async with self._refresh_lock:
            now = datetime.now(UTC)
            if self._last_attempt_at and (now - self._last_attempt_at).total_seconds() < 90:
                cached = self.snapshot()
                cached["cached"] = True
                return cached
            self._last_attempt_at = now
            errors: list[str] = []
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
            }
            async with httpx.AsyncClient(follow_redirects=True, headers=headers) as session:
                # 연속 실패한 소스는 이번 회차를 건너뛴다(백오프). 82cook이 요청 빈도로
                # IP 단위 차단을 걸었을 때 수집기가 5분마다 계속 찌르고 있었다.
                active_sources = [
                    source for source in DIRECT_COMMUNITY_SOURCES
                    if not self._backoff.should_skip(str(source["key"]), now)
                ]
                skipped = [s for s in DIRECT_COMMUNITY_SOURCES if s not in active_sources]
                results = await asyncio.gather(
                    session.get(FMKOREA_HUMOR_URL, timeout=httpx.Timeout(12.0, connect=5.0)),
                    session.get(ISSUELINK_URL, timeout=httpx.Timeout(12.0, connect=5.0)),
                    *(
                        session.get(source["url"], timeout=httpx.Timeout(12.0, connect=5.0))
                        for source in active_sources
                    ),
                    return_exceptions=True,
                )

            fmkorea_items: list[dict[str, Any]] = []
            issue_ids: set[str] = set()
            issue_items: list[dict[str, Any]] = []
            fmkorea_ok = False
            issuelink_ok = False
            direct_source_health: dict[str, bool] = {}
            expanded_direct_items: list[dict[str, Any]] = []
            if isinstance(results[0], Exception):
                errors.append("FMKorea 직접 목록 수집 실패")
            else:
                # FMKorea는 자동 접근을 보안 시스템으로 막는다(2026-08-06 확인: HTTP 430 +
                # "에펨코리아 보안 시스템" 페이지, robots.txt도 대부분의 봇에 메인만 허용).
                # 헤더를 위장해 뚫지 않는다 — AAGAG를 robots 이유로 제외한 것과 같은 기준이다.
                # 원인을 "파싱 실패"로 뭉개면 고칠 수 있는 버그처럼 보이므로 차단은 따로 적는다.
                if _looks_blocked(results[0]):
                    errors.append("FMKorea 자동 접근 차단 — IssueLink 경유로만 확인")
                else:
                    try:
                        results[0].raise_for_status()
                        fmkorea_items = parse_fmkorea_latest(results[0].text, now=now)
                        fmkorea_ok = bool(fmkorea_items)
                        if not fmkorea_items:
                            errors.append("FMKorea 직접 목록이 비어 있음")
                    except Exception:
                        errors.append("FMKorea 직접 목록 파싱 실패")
            if isinstance(results[1], Exception):
                errors.append("IssueLink 비교 수집 실패")
            else:
                try:
                    results[1].raise_for_status()
                    issue_ids = parse_issuelink_fmkorea_ids(results[1].text)
                    issue_items = parse_issuelink_community_items(results[1].text)
                    issuelink_ok = bool(issue_ids)
                except Exception:
                    errors.append("IssueLink 비교 파싱 실패")

            for source in skipped:
                key = str(source["key"])
                direct_source_health[key] = False
                resume = self._backoff.status(now).get(key, {}).get("resume_in_minutes", 0)
                errors.append(f"{source['label']} 연속 실패로 대기 중({resume}분 후 재시도)")

            for source, result in zip(active_sources, results[2:], strict=True):
                key = str(source["key"])
                label = str(source["label"])
                if isinstance(result, Exception):
                    direct_source_health[key] = False
                    self._backoff.record_failure(key, now)
                    errors.append(f"{label} 직접 목록 수집 실패")
                    continue
                if _looks_blocked(result):
                    direct_source_health[key] = False
                    self._backoff.record_failure(key, now)
                    errors.append(f"{label} 자동 접근 차단 — 요청 간격을 늘려 재시도")
                    continue
                try:
                    result.raise_for_status()
                    parsed = parse_direct_community_source(key, result.text, now=now)
                    direct_source_health[key] = bool(parsed)
                    expanded_direct_items.extend(parsed)
                    if parsed:
                        self._backoff.record_success(key)
                    else:
                        errors.append(f"{label} 직접 목록이 비어 있음")
                except Exception:
                    direct_source_health[key] = False
                    errors.append(f"{label} 직접 목록 파싱 실패")

            previous = self._load_previous()
            previous_items = previous.get("items", {}) if isinstance(previous.get("items"), dict) else {}
            previous_at_raw = str(previous.get("polled_at") or "")
            try:
                previous_at = datetime.fromisoformat(previous_at_raw)
                if previous_at.tzinfo is None:
                    previous_at = previous_at.replace(tzinfo=UTC)
                elapsed_minutes = max((now - previous_at.astimezone(UTC)).total_seconds() / 60, 0.1)
            except ValueError:
                elapsed_minutes = 0.0

            direct_observations = [
                {
                    **item,
                    "community_source": "fmkorea",
                    "community_label": "FMKorea",
                    "source_position": position,
                    "link_kind": "publisher_original",
                    "signal_source": "직접 목록",
                }
                for position, item in enumerate(fmkorea_items)
            ] + expanded_direct_items
            _annotate_community_clusters(direct_observations)
            self.lead_tracker.record_observations(direct_observations, issue_items, observed_at=now)
            direct_keys = {_snapshot_item_key(item) for item in direct_observations}
            issue_keys = {_snapshot_item_key(item) for item in issue_items}

            qualified: list[dict[str, Any]] = []
            blocked_count = 0
            excluded_topics: Counter[str] = Counter()
            for item in direct_observations:
                age = item.get("age_minutes")
                exclusion = excluded_topic_reason(item["title"], item.get("category"))
                if exclusion:
                    excluded_topics[exclusion] += 1
                    continue
                if (
                    age is None
                    or age > _direct_max_age_minutes()
                    or not has_min_traction(item)
                    or not _is_brand_safe_title(item["title"])
                ):
                    blocked_count += 1
                    continue
                source_key = str(item.get("community_source") or "fmkorea")
                observation = self.exposure_tracker.record(
                    f"community:direct:{source_key}:{item['id']}",
                    {
                        "original_count": 1,
                        "source_count": 1,
                        "mentions": 1,
                        "comments": item["comments"],
                    },
                    observed_at=now,
                    score_version=_COMMUNITY_EXPOSURE_SCORE_VERSION,
                )
                previous_item = previous_items.get(_snapshot_item_key(item), {})
                if not previous_item and source_key == "fmkorea":
                    previous_item = previous_items.get(item["id"], {})
                delta_rate = 0.0
                if elapsed_minutes > 0 and isinstance(previous_item, dict):
                    delta_rate = max(0, item["views"] - int(previous_item.get("views") or 0)) / elapsed_minutes
                aggregator_available = bool(issue_items)
                before_issuelink = aggregator_available and _snapshot_item_key(item) not in issue_keys
                score, effective_rate = _direct_signal_score(
                    age_minutes=age,
                    views=item["views"],
                    comments=item["comments"],
                    votes=item["votes"],
                    delta_views_per_minute=delta_rate,
                    before_issuelink=before_issuelink,
                )
                # 커널 판정을 게이트 안으로 들인다. 예전에는 조회 속도로 12건을 고른 뒤
                # 라우터에서 판정을 붙였기 때문에, 판정은 표시 순서만 바꾸고 무엇을 남길지에는
                # 아무 영향이 없었다. 사는 축(가해자 명확·낙차)은 확산이 덜 붙었어도 통과시킨다 —
                # X에서 판정이 붙는 소재는 조회가 늦게 오기 때문이다.
                screen = screen_material(item["title"], community_label=item.get("community_label"))
                item["kernel_screen"] = screen
                live_axis = str(screen.get("axis", "")).startswith("live")
                if not passes_spread_gate(item, score=score, live_axis=live_axis):
                    continue
                cross_source_count = int(item.get("cross_community_source_count") or 1)
                cross_boost = min(15, max(0, cross_source_count - 1) * 8)
                exposure_score = min(100, score + cross_boost)
                encoded = quote(item["title"])
                exposure_reasons = [
                    f"게시 후 {age}분",
                    "IssueLink 선행 감지" if before_issuelink else "IssueLink 노출 확인",
                ]
                if effective_rate is not None:
                    exposure_reasons.insert(0, f"분당 조회 {effective_rate:.1f}")
                else:
                    exposure_reasons.insert(0, f"추천·댓글 {item['votes'] + item['comments']:,}개")
                if cross_source_count >= 2:
                    exposure_reasons.append(f"직접 커뮤니티 {cross_source_count}곳 동시 확산")
                qualified.append(
                    {
                        **item,
                        "early_score": score,
                        "x_exposure_score": exposure_score,
                        "exposure_breakdown": {"direct_velocity": score, "cross_community": cross_boost},
                        "exposure_reasons": exposure_reasons,
                        "score_version": _COMMUNITY_EXPOSURE_SCORE_VERSION,
                        "exposure_confidence": "high" if previous_item else "medium",
                        "exposure_coverage": 1.0 if previous_item else 0.92,
                        "observed_at": observation["observed_at"],
                        "observation_delta": observation,
                        "views_per_minute": round(effective_rate, 1) if effective_rate is not None else None,
                        "delta_views_per_minute": round(delta_rate, 1),
                        "before_issuelink": before_issuelink,
                        "issuelink_status": (
                            "아직 IssueLink 미노출"
                            if before_issuelink
                            else (
                                "IssueLink 노출 확인"
                                if _snapshot_item_key(item) in issue_keys
                                else "IssueLink 비교 불가"
                            )
                        ),
                        "x_search_url": f"https://x.com/search?q={encoded}&src=typed_query&f=live",
                        "threads_search_url": f"https://www.threads.com/search?q={encoded}",
                        **self.lead_tracker.metrics_for(item),
                    }
                )

            qualified.sort(
                key=lambda item: (
                    item["x_exposure_score"],
                    item["before_issuelink"],
                    item["views_per_minute"] or 0,
                ),
                reverse=True,
            )
            # 라운드로빈이 소스당 1건씩만 남기면 "오늘 유난히 좋은 소스"의 상위 글이 통째로
            # 밀려난다. 풀을 넓게 잡아 뒤의 커널 정렬이 고를 여지를 남긴다.
            qualified = _select_diverse_community_items(qualified, limit * 3)
            any_direct_ok = fmkorea_ok or any(direct_source_health.values())
            fallback_mode = not any_direct_ok and bool(issue_items)
            resolved_originals = 0
            # 애그리게이터 몫을 미리 떼어 둔다. 예전에는 직접 목록이 자리를 다 채우면
            # IssueLink를 아예 보지 않았는데, 그러면 클리앙·인벤·뽐뿌·82cook처럼 직접
            # 수집이 막혔거나 붙이지 않은 커뮤니티가 영영 화면에 오르지 못한다.
            quota = aggregator_quota(limit, any_direct_ok=any_direct_ok)
            if issue_items:
                allowed_issue_items: list[dict[str, Any]] = []
                for item in issue_items:
                    if _snapshot_item_key(item) in direct_keys:
                        continue
                    # 라벨은 출처지 주제가 아니다. 넣으면 MLB파크가 "mlb"에 걸려 전량 사라진다.
                    exclusion = excluded_topic_reason(item["title"])
                    if exclusion:
                        excluded_topics[exclusion] += 1
                        continue
                    if not _is_brand_safe_title(item["title"]):
                        blocked_count += 1
                        continue
                    allowed_issue_items.append(item)
                _annotate_community_clusters(allowed_issue_items)
                observations_by_cluster: dict[str, dict[str, Any]] = {}
                for item in allowed_issue_items:
                    cluster_key = str(item["community_cluster_key"])
                    if cluster_key in observations_by_cluster:
                        continue
                    cluster = [
                        candidate
                        for candidate in allowed_issue_items
                        if candidate.get("community_cluster_key") == cluster_key
                    ]
                    observations_by_cluster[cluster_key] = self.exposure_tracker.record(
                        f"community:cluster:{cluster_key}",
                        {
                            "original_count": len(cluster),
                            "source_count": len({candidate["community_source"] for candidate in cluster}),
                            "mentions": len(cluster),
                            "comments": sum(int(candidate.get("comments") or 0) for candidate in cluster),
                        },
                        observed_at=now,
                        score_version=_COMMUNITY_EXPOSURE_SCORE_VERSION,
                    )
                for item in allowed_issue_items:
                    observation = observations_by_cluster[str(item["community_cluster_key"])]
                    (
                        exposure_score,
                        exposure_breakdown,
                        exposure_reasons,
                        exposure_confidence,
                        exposure_coverage,
                    ) = _community_x_exposure_assessment(item, observation)
                    item["x_exposure_score"] = exposure_score
                    item["exposure_breakdown"] = exposure_breakdown
                    item["exposure_reasons"] = exposure_reasons
                    item["score_version"] = _COMMUNITY_EXPOSURE_SCORE_VERSION
                    item["exposure_confidence"] = exposure_confidence
                    item["exposure_coverage"] = exposure_coverage
                    item["observed_at"] = observation["observed_at"]
                    item["observation_delta"] = observation
                selected_issue_items = _select_diverse_community_items(allowed_issue_items, quota)
                if selected_issue_items:
                    # 확보한 자리만큼 직접 목록을 덜어낸다. 점수 순으로만 자르면 확산이 덜 붙은
                    # 사는 축 소재가 가장 먼저 사라지므로, 여기서도 커널 축을 1차 키로 둔다.
                    qualified = sort_by_kernel(qualified)[: max(0, limit - len(selected_issue_items))]
                async with httpx.AsyncClient(headers=headers, follow_redirects=False) as redirect_session:
                    resolved_originals = await _resolve_community_origins(redirect_session, selected_issue_items)
                for item in selected_issue_items:
                    encoded = quote(item["title"])
                    qualified.append(
                        {
                            **item,
                            "early_score": None,
                            "views_per_minute": None,
                            "delta_views_per_minute": None,
                            "before_issuelink": False,
                            "issuelink_status": "IssueLink 집계 확인",
                            "signal_source": "IssueLink",
                            "x_search_url": f"https://x.com/search?q={encoded}&src=typed_query&f=live",
                            "threads_search_url": f"https://www.threads.com/search?q={encoded}",
                            **self.lead_tracker.metrics_for(item),
                        }
                    )
            if direct_observations:
                self._save_current(now, direct_observations)
            self.exposure_tracker.save(now=now)
            # 자를 때도 커널을 본다. 게이트에는 판정을 들였는데(passes_spread_gate) 마지막
            # 자르기가 점수 순이라, 통과시킨 사는 축 소재가 여기서 다시 잘리고 있었다 —
            # 확산이 덜 붙어 점수가 낮다는 것이 사는 축 소재의 정의라 언제나 맨 아래로 간다.
            # 2026-08-07 실측: 게이트만 면제했을 때 화면의 사는 축은 여전히 2건이었다.
            # IssueLink 경유 항목은 아직 판정이 없으니 여기서 붙여 같은 잣대로 겨루게 한다.
            for item in qualified:
                if "kernel_screen" not in item:
                    item["kernel_screen"] = screen_material(
                        item.get("title", ""), community_label=item.get("community_label")
                    )
            displayed = sort_by_kernel(qualified)[:limit]
            # 0002: 제목만으로 약하게 판정된 소재는 본문(og:description)을 한 번 더 본다.
            og_enrichment = await _apply_og_second_pass(
                displayed,
                source_backoff=self._backoff,
            )
            # 2차 판정이 축을 바꿀 수 있으므로 여기서 한 번 더 정렬한다. 이게 없으면
            # 본문을 보고 사는 축으로 올라온 소재가 화면 맨 아래에 남는다 — 0002가
            # 판정을 고쳐 놓고도 순서에는 반영되지 않는 셈이 된다.
            displayed = sort_by_kernel(displayed)
            self._snapshot = {
                "available": bool(displayed),
                "items": displayed,
                "total_direct_posts": len(direct_observations),
                "direct_source_count": sum(1 for healthy in {"fmkorea": fmkorea_ok, **direct_source_health}.values() if healthy),
                # 분모를 화면에 하드코딩하면 소스를 늘려도 옛 숫자가 남는다. FMKorea 자리를 포함해 보낸다.
                "direct_source_total": len(DIRECT_COMMUNITY_SOURCES) + 1,
                "direct_displayed_count": sum(1 for item in displayed if item.get("signal_source") == "직접 목록"),
                "qualified_count": len(displayed),
                "before_issuelink_count": sum(1 for item in displayed if item["before_issuelink"]),
                "filtered_count": max(0, len(direct_observations) - sum(1 for item in qualified if item.get("signal_source") == "직접 목록")),
                "brand_safety_blocked_count": blocked_count,
                "excluded_topic_counts": dict(excluded_topics),
                "fallback_mode": fallback_mode,
                "community_source_count": len({item.get("community_source") for item in displayed}),
                "resolved_original_count": resolved_originals,
                "measured_lead_count": sum(1 for item in displayed if item.get("lead_status") == "measured"),
                "refreshed_at": now.isoformat(),
                "poll_interval_seconds": 120,
                "source_health": {
                    "fmkorea_direct": fmkorea_ok,
                    **{f"{key}_direct": healthy for key, healthy in direct_source_health.items()},
                    "issuelink_confirmation": issuelink_ok,
                    "community_original_redirects": resolved_originals > 0,
                    "aagag": False,
                },
                "errors": errors,
                "og_enrichment": og_enrichment,
                "notice": (
                    "직접 커뮤니티 수집이 모두 제한 중입니다. IssueLink에서 확인한 원문만 표시하며 선행으로 계산하지 않습니다."
                    if fallback_mode
                    else "개드립·더쿠·루리웹·FMKorea 직접 감지와 IssueLink 최초 감지의 실제 시각 차이만 표시합니다."
                ),
            }
            return self.snapshot()
