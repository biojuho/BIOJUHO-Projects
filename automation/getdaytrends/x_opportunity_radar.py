"""Live breaking-news and viral-topic radar for X content planning."""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlparse

import httpx

if TYPE_CHECKING:
    from pathlib import Path

try:
    from .breaking_news_observer import BreakingNewsObserver
    from .collectors.daum_realtime import _async_fetch_daum_realtime
    from .collectors.news_rankings import _async_fetch_news_rankings
    from .collectors.reddit import _async_fetch_reddit_hot
    from .collectors.sources import _async_fetch_getdaytrends, _async_fetch_google_trends_rss
    from .content_filters import excluded_topic_reason
    from .exposure_observation_tracker import ExposureObservationTracker
    from .filter_eval.shadow_store import FilterShadowStore, record_filter_candidate_fail_open
    from .models import RawTrend
    from .news_origin_collector import fetch_bing_news_origins
    from .threads_signal_collector import ThreadsSignalCollector
except ImportError:
    from breaking_news_observer import BreakingNewsObserver
    from collectors.daum_realtime import _async_fetch_daum_realtime
    from collectors.news_rankings import _async_fetch_news_rankings
    from collectors.reddit import _async_fetch_reddit_hot
    from collectors.sources import _async_fetch_getdaytrends, _async_fetch_google_trends_rss
    from content_filters import excluded_topic_reason
    from exposure_observation_tracker import ExposureObservationTracker
    from filter_eval.shadow_store import FilterShadowStore, record_filter_candidate_fail_open
    from models import RawTrend
    from news_origin_collector import fetch_bing_news_origins
    from threads_signal_collector import ThreadsSignalCollector


TrendFetcher = Callable[[httpx.AsyncClient, str, int], Awaitable[list[RawTrend]]]
NewsFetcher = Callable[[httpx.AsyncClient, str, int], Awaitable[list[dict[str, Any]]]]
RankingFetcher = Callable[[httpx.AsyncClient, int], Awaitable[list[dict[str, Any]]]]
DaumFetcher = Callable[[httpx.AsyncClient, int], Awaitable[tuple[str | None, list[dict[str, Any]]]]]
RedditFetcher = Callable[[httpx.AsyncClient, int], Awaitable[list[dict[str, Any]]]]

_FALLBACK_X_TOPICS = {"주말 계획", "점심 메뉴", "날씨", "커피", "퇴근"}
_X_EXPOSURE_SCORE_VERSION = "x-exposure-v3"
_NEWS_AGGREGATOR_DOMAINS = ("v.daum.net", "news.nate.com", "news.zum.com", "msn.com")
_NEWS_AGGREGATOR_SOURCES = {"daum", "nate", "zum", "msn"}
_SPAM_REASON_PREFIX = "스팸·불법광고 패턴"
_SPAM_TREND_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b라인\s*[a-z0-9_]{2,}", "연락처 유도(라인 ID)"),
    (r"\bqq\s*\d{2,}", "연락처 유도(QQ ID)"),
    (r"\b카톡\s*(연락|문의|상담|가능|[a-z0-9_]{2,})", "연락처 유도(카톡)"),
    (r"\b빠른\s*이동\b", "연락처 유도(빠른이동)"),
    (r"\b(출장|만남)\b.*\b(만남|출장)\b", "출장·만남 광고"),
    (
        r"\b(무직자\s*대출|작업\s*대출|소액\s*결제|대출\s*(가능|상담|문의|진행중|한도)|후불\s*(결제|폰|유심))\b",
        "대출·후불 광고",
    ),
)
_CATEGORY_TERMS = {
    "생활·경제": ("지원금", "물가", "소비자", "공공요금"),
    "테크·AI": ("ai", "인공지능", "테슬라", "반도체", "하이닉스", "오픈ai", "구글", "애플", "로봇"),
    "연예·방송": ("배우", "가수", "아이돌", "예능", "드라마", "영화", "방송", "콘서트"),
    "건강·안전": ("태풍", "지진", "사고", "화재", "질병", "백신", "화이자", "의료", "사망"),
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_keyword(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


_HANGUL_PATTERN = re.compile(r"[가-힣]")


def _has_hangul(text: str) -> bool:
    return bool(_HANGUL_PATTERN.search(str(text or "")))


def _age_minutes(published_at: datetime | None, now: datetime) -> int | None:
    if published_at is None:
        return None
    normalized = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
    return max(0, round((now - normalized.astimezone(UTC)).total_seconds() / 60))


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or ""))
        except (TypeError, ValueError):
            return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def _first_seen_at(
    tracker: ExposureObservationTracker,
    key: str,
    now: datetime,
) -> str | None:
    """Return the earliest retained observation without inventing damaged history."""
    state = getattr(tracker, "_state", None)
    series_by_key = state.get("series") if isinstance(state, dict) else None
    if not isinstance(series_by_key, dict):
        return None
    points = series_by_key.get(key)
    if points is None or points == []:
        return now.astimezone(UTC).isoformat()
    if not isinstance(points, list) or not isinstance(points[0], dict):
        return None
    first_point = points[0]
    parsed = _timestamp(first_point.get("first_seen_at") or first_point.get("observed_at"))
    if parsed is None or parsed > now.astimezone(UTC):
        return None
    return parsed.isoformat()


def _age_fields(
    *,
    source_published_at: datetime | None,
    first_seen_at: str | None,
    now: datetime,
) -> tuple[int | None, str, str]:
    if source_published_at is not None:
        age = _age_minutes(source_published_at, now)
        basis = "source_published_at"
    else:
        first_seen = _timestamp(first_seen_at)
        age = _age_minutes(first_seen, now) if first_seen is not None and first_seen <= now else None
        basis = "first_seen_at" if age is not None else "unknown"
    return age, basis, f"{age}분" if age is not None else "미상"


# 0099: 「최근 게시」와 「긴급 사건」은 다르다. 연합뉴스 RSS의 모든 새 글을
# 속보로 부르면 칼럼·전시·일상 날씨도 속보처럼 보인다(0099 시작 실측 — 속보
# 20건 중 긴급 증거가 있는 것은 소수였다). 사건·안전·긴급 증거 어휘가 있는
# 글만 지금 속보로 올리고 나머지는 «최신 뉴스» lane으로 내려 보낸다.
_URGENT_EVIDENCE_TERMS = (
    "사고",
    "화재",
    "전소",
    "소화",
    "연기흡입",
    "사망",
    "숨져",
    "숨진",
    "중상",
    "실종",
    "구조",
    "대피",
    "대피령",
    "붕괴",
    "추락",
    "전복",
    "폭발",
    "유출",
    "누출",
    "오염",
    "방사능",
    "지진",
    "강진",
    "태풍",
    "허리케인",
    "해일",
    "산불",
    "침수",
    "정전",
    "확산",
    "감염",
    "특보",
    "주의보",
    "경보",
    "긴급",
    "속보",
    "총격",
    "발포",
    "흉기",
    "폭행",
    "살해",
    "살인",
    "인질",
    "협박",
    "체포",
    "검거",
    "구속",
    "자수",
    "입건",
    "탈주",
    "탈옥",
    "사라진",
)
# 「~에서 불」 표현은 어휘 목록에 넣을 수 없다(불법·불안·불구 등이 붙는다).
# 뒤에 이어지는 글자로 흔한 합성어를 걸러 낸다(예: 「아파트서 불…4명 연기흡입」).
_URGENT_EVIDENCE_PATTERNS = (
    re.compile(r"서\s*불(?![법구안미동행씩나무를이다은는])"),
    re.compile(r"불이\s*(?:나|터|번지)"),
)


def _breaking_urgency_evidence(keyword: str, summary: str, source: str) -> tuple[str, str]:
    """후보 하나를 지금 속보(urgent)와 최신 뉴스(latest)로 가른다.

    기상청(kma:*) 4개 연산은 전부 특보·발표 계열이라 안전 증거 그 자체다.
    연합뉴스는 제목·요약에서 사건·안전·긴급 어휘를 찾고, 증거가 없으면
    최신 원문으로만 취급한다. 반환값: (urgency, 근거 표시 문구).
    """
    if source.startswith("kma:"):
        return "urgent", "기상청 특보·발표 계열"
    text = re.sub(r"\s+", " ", f"{keyword} {summary}").strip()
    for term in _URGENT_EVIDENCE_TERMS:
        if term in text:
            return "urgent", f"긴급 증거 «{term}»"
    for pattern in _URGENT_EVIDENCE_PATTERNS:
        if pattern.search(text):
            return "urgent", "긴급 증거 «화재 표현»"
    return "latest", "긴급 증거 없음 — 최신 원문"


def _breaking_lane_items(
    raw_candidates: object,
    now: datetime,
    *,
    limit: int,
    excluded_reasons: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw_candidates, list):
        return []
    urgent_items: list[dict[str, Any]] = []
    latest_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        candidate_id = str(raw.get("id") or "").strip()
        keyword = str(raw.get("keyword") or "").strip()
        source = str(raw.get("source") or "").strip()
        if (
            not candidate_id
            or candidate_id in seen_ids
            or not keyword
            or (source != "yonhap-rss" and not source.startswith("kma:"))
        ):
            continue
        seen_ids.add(candidate_id)
        summary = str(raw.get("summary") or "").strip()
        # 0099: 관측 단계에서 이미 걸렀어야 할 금지 주제가 여기까지 새면(관측 우회
        # 주입·향후 회귀) lane이 스스로 막는다. 사유는 세어 응답에 공개한다.
        reason = excluded_topic_reason(keyword, summary)
        if reason:
            if excluded_reasons is not None:
                excluded_reasons[reason] += 1
            continue
        source_label = "연합뉴스" if source == "yonhap-rss" else "기상청"
        urgency, urgency_evidence = _breaking_urgency_evidence(keyword, summary, source)
        published_at = _timestamp(raw.get("source_published_at"))
        source_published_at = published_at.isoformat() if published_at is not None else None
        delay = None
        if published_at is not None:
            delay = round(max(0.0, (now.astimezone(UTC) - published_at).total_seconds() / 60), 1)
        age_minutes, age_basis, age_display = _age_fields(
            source_published_at=published_at,
            first_seen_at=None,
            now=now,
        )
        source_url = str(raw.get("source_url") or "").strip()
        if source_url and urlparse(source_url).scheme not in {"http", "https"}:
            source_url = ""
        item = {
            "id": candidate_id,
            "keyword": keyword,
            # 0072: 상류(0069)가 실은 원문 단을 통과시킨다. 없으면 빈 문자열이고
            # 제목(keyword)을 복사해 만들지 않는다 — 요약 생성 금지 규칙 그대로.
            "summary": summary,
            # 0099: 긴급 증거가 있는 글만 «속보·공적발표»다. dashboard.py가 이 lane
            # 이름으로 관측 단어 재등록을 막으므로 문자열은 그대로 둔다.
            "lane": "속보·공적발표" if urgency == "urgent" else "최신 뉴스",
            "category": "공적 발표" if urgency == "urgent" else "최신 원문",
            "urgency": urgency,
            "urgency_evidence": urgency_evidence,
            "qualification_mode": "public_source_breaking" if urgency == "urgent" else "public_source_latest",
            "context_level": "source_direct",
            "materiality_pass": True,
            "observed_at": now.astimezone(UTC).isoformat(),
            "source": source,
            "sources": [source_label],
            "source_published_at": source_published_at,
            "detection_delay_minutes": delay,
            "detection_delay_display": f"{delay:.1f}분" if delay is not None else "미상",
            "first_seen_at": None,
            "age_minutes": age_minutes,
            "age_basis": age_basis,
            "age_display": age_display,
            "source_url": source_url,
            "volume": "N/A",
            "volume_numeric": 0,
            "news_headlines": [],
            "news_items": [],
            "threads_posts": [],
            "threads_author_count": 0,
            "reasons": [
                f"{source_label} 직접 발표 · {urgency_evidence} · 기존 점수열과 분리",
            ],
        }
        (urgent_items if urgency == "urgent" else latest_items).append(item)

    def _recency_key(item: dict[str, Any]) -> tuple[bool, int]:
        # 시각을 아는 글이 앞(최신순), 시각 미상은 계층 맨 뒤로 강등한다.
        age = item["age_minutes"]
        return (age is None, age if age is not None else 0)

    urgent_items.sort(key=_recency_key)
    latest_items.sort(key=_recency_key)
    return [*urgent_items, *latest_items][:limit]


def _spam_trend_reason(keyword: str) -> str | None:
    """X 트렌드 단어에 대한 소스 품질 스팸 판정.

    안전 게이트(HARD_SAFETY_PATTERNS)가 아니라 후보 구성 단계의 품질
    필터다. 실측된 광고 형태만 죽인다: 연락처 유도(라인·QQ·카톡 ID),
    출장·만남 조합, 빠른이동, 대출·후불 광고. 「군인 가능」 같은
    무맥락 단어는 여기서 죽이면 안 된다(오탐).
    """
    text = re.sub(r"\s+", " ", str(keyword or "")).strip()
    if not text:
        return None
    for pattern, label in _SPAM_TREND_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return f"{_SPAM_REASON_PREFIX}({label})"
    return None


def _parse_daum_rank_status(value: object) -> int | str | None:
    """다음 실시간 트렌드 status 실물 부호화(0072 실측).

    실물 JSON은 `"new"`·`"-12"`·`"0"` 같은 문자열이고 수집기가 숫자는
    int로 정규해 준다. 신규 진입을 뜻하는 값은 0이 아니라 `"new"`다 —
    0068 브리프의 «0=신규» 기재가 틀렸고(0071 반증), 0은 변동 없음이다.
    `"new"`는 계단 수와 섞이지 않도록 문자열 그대로 보존한다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip().casefold()
    if not text:
        return None
    if text == "new":
        return "new"
    try:
        return int(text)
    except ValueError:
        return None


def _rank_status_display(status: int | str) -> str:
    if status == "new":
        return "신규 진입"
    if status == 0:
        return "순위 변동 없음"
    if status > 0:
        return f"{status}계단 상승"
    return "1계단 하락" if status == -1 else f"{-status}계단 하락"


def _daum_trend_items(
    raw_items: list[dict[str, Any]],
    now: datetime,
    *,
    filter_shadow_store: FilterShadowStore | None = None,
    excluded_reasons: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    """다음 실시간 트렌드(1순위 소스)를 점수 없는 후보로 정규화한다.

    `status`(순위 변동)가 「왜 지금 뜨는가」 신호다. 순위 순서는 그대로
    보존하고 점수는 만들지 않는다.
    """
    items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for raw in raw_items:
        keyword = str(raw.get("keyword") or "").strip()
        status = _parse_daum_rank_status(raw.get("status"))
        if not keyword or status is None:
            continue
        key = _normalize_keyword(keyword)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        reason = excluded_topic_reason(keyword)
        record_filter_candidate_fail_open(
            filter_shadow_store,
            source="x-radar",
            candidate_id=hashlib.sha256(keyword.casefold().encode("utf-8")).hexdigest()[:16],
            title=keyword,
            extra_text="다음 실시간 트렌드",
            filter_verdict="block" if reason else "allow",
            filter_reason=reason or "",
            observed_at=now,
        )
        if reason:
            if excluded_reasons is not None:
                excluded_reasons[reason] += 1
            continue
        url = str(raw.get("url") or "").strip()
        if urlparse(url).scheme not in {"http", "https"}:
            url = ""
        display_rank = raw.get("display_rank")
        if not isinstance(display_rank, int):
            display_rank = raw.get("rank")
        observed_at = now.astimezone(UTC).isoformat()
        # 0077: 수집기의 `updatedAt`(=`source_published_at`으로 복제돼 온다)는 트렌드
        # «목록»의 갱신 시각이다 — 한 번 불러온 키워드 전부가 같은 값을 공유하므로
        # 개별 사건의 발표 시각이 아니다. 발표 시각으로 쓰면 며칠 된 트렌드도 방금
        # 발표된 것처럼 보인다(0064 규약 위반). 항목별 시각 신호는 이 파이프라인이
        # 그 키워드를 처음 본 `first_seen_at`뿐이므로 관측 시각으로 싣는다.
        # 목록 갱신 시각 자체는 아래 `updated_at`에 이미 표시돼 있다.
        first_seen_at = str(raw.get("first_seen_at") or "").strip() or None
        age_minutes, age_basis, age_display = _age_fields(
            source_published_at=None,
            first_seen_at=first_seen_at,
            now=now,
        )
        items.append(
            {
                "id": hashlib.sha256(keyword.casefold().encode("utf-8")).hexdigest()[:16],
                "keyword": keyword,
                "lane": "다음 실시간 트렌드",
                "category": _topic_category(keyword, []),
                "qualification_mode": "daum_realtime_trend",
                "context_level": "source_direct",
                "materiality_pass": True,
                "observed_at": observed_at,
                "source": "다음 실시간 트렌드",
                "publisher": "",
                "sources": ["다음 실시간 트렌드"],
                "rank": display_rank,
                "rank_status": status,
                "rank_status_display": _rank_status_display(status),
                # 0077: 수집기의 키워드 이력 판정(신규 관측)을 사실 그대로 통과시킨다.
                "is_new": raw.get("is_new") is True,
                "source_published_at": None,
                "first_seen_at": first_seen_at,
                "age_minutes": age_minutes,
                "age_basis": age_basis,
                "age_display": age_display,
                "source_url": url,
                "volume": "N/A",
                "volume_numeric": 0,
                "news_headlines": [],
                "news_items": [],
                "first_report": None,
                "threads_posts": [],
                "threads_author_count": 0,
                "x_signal_keywords": [],
                "x_search_url": "",
                "updated_at": str(raw.get("updated_at") or ""),
                "reasons": [f"다음 실시간 트렌드 {display_rank}위 · {_rank_status_display(status)}"],
            }
        )
    return items


def _news_ranking_items(
    raw_items: list[dict[str, Any]],
    now: datetime,
    *,
    filter_shadow_store: FilterShadowStore | None = None,
    excluded_reasons: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    """뉴스 랭킹 원문을 점수 없는 후보로 정규화한다. 순서는 그대로 보존한다."""
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for raw in raw_items:
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or "").strip()
        source = str(raw.get("source") or "").strip() or "뉴스 랭킹"
        publisher = str(raw.get("publisher") or "").strip()
        rank = raw.get("rank")
        if not title or not url or urlparse(url).scheme not in {"http", "https"}:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        reason = excluded_topic_reason(title)
        record_filter_candidate_fail_open(
            filter_shadow_store,
            source="x-radar",
            candidate_id=hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:16],
            title=title,
            extra_text=f"{source} {publisher}".strip(),
            filter_verdict="block" if reason else "allow",
            filter_reason=reason or "",
            observed_at=now,
        )
        if reason:
            if excluded_reasons is not None:
                excluded_reasons[reason] += 1
            continue
        observed_at = now.astimezone(UTC).isoformat()
        # 0072: 랭킹 raw는 게시시각(source_published_at·first_seen_at)을 실어 주는데
        # 화이트리스트가 버려서 «미상»으로 내보냈다. 맥락이니 통과시킨다.
        source_published = _timestamp(raw.get("source_published_at") or raw.get("published_at"))
        source_published_at = source_published.isoformat() if source_published is not None else None
        first_seen_at = str(raw.get("first_seen_at") or "").strip() or None
        age_minutes, age_basis, age_display = _age_fields(
            source_published_at=source_published,
            first_seen_at=first_seen_at,
            now=now,
        )
        # 0077: 수집기(0073)가 순위 스냅샷으로 계산해 실어 주는 신호를 통과시킨다.
        # 신규 진입·계단 수는 사실이고 점수로 환산하지 않는다(0053). 프로세스 첫
        # 스냅샷에서는 전항이 신규 관측(is_new=True, rank_change=None)으로 나오는
        # 것이 수집기 이력의 정직한 초기 상태다.
        rank_change_raw = raw.get("rank_change")
        rank_change = (
            rank_change_raw
            if isinstance(rank_change_raw, int) and not isinstance(rank_change_raw, bool)
            else None
        )
        status_raw = raw.get("status")
        rank_status = (
            str(status_raw).strip()
            if isinstance(status_raw, (int, str)) and not isinstance(status_raw, bool)
            else None
        )
        item = {
            "id": hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:16],
            "keyword": title,
            "lane": "뉴스 랭킹",
            "category": _topic_category(title, [title]),
            "qualification_mode": "news_ranking",
            "context_level": "source_direct",
            "materiality_pass": True,
            "observed_at": observed_at,
            "source": source,
            "publisher": publisher,
            "sources": [source],
            "rank": rank,
            "is_new": raw.get("is_new") is True,
            "rank_change": rank_change,
            "rank_status": rank_status,
            "source_published_at": source_published_at,
            "first_seen_at": first_seen_at,
            "age_minutes": age_minutes,
            "age_basis": age_basis,
            "age_display": age_display,
            "source_url": url,
            "volume": "N/A",
            "volume_numeric": 0,
            "news_headlines": [title],
            "news_items": [{"title": title, "url": url, "source": publisher or source}],
            "first_report": None,
            "threads_posts": [],
            "threads_author_count": 0,
            "x_signal_keywords": [],
            "x_search_url": "",
            "reasons": [f"{source} {rank}위"],
        }
        items.append(item)
    return items


# 0099: 뉴스 랭킹 lane에는 독립적인 최대 나이가 없어 430분·1,870분 표본이 그대로
# 통과했다(시작 실측). «오늘 이슈»가 막 지난 글을 말하도록 상한을 둔다. 360분은
# _freshness_points의 신선도 구간 경계와 같은 값이다.
_NEWS_RANKING_MAX_AGE_MINUTES = 360


def _apply_news_ranking_freshness_policy(
    items: list[dict[str, Any]],
    *,
    excluded_reasons: Counter[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """나이 상한 초과 랭킹을 걷어내고, 시각 미상 항목은 lane 하단으로 강등한다.

    `_news_ranking_items`는 순위 순서를 보존하는 순수 정규화기다(0077 규약).
    나이 정책은 이렇게 refresh() 안에서 별도 계층으로 붙인다. 반환: (정책
    적용된 목록, 강등된 항목 수). 제거 사유는 excluded_reasons에 합산한다.
    """
    fresh: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []
    for item in items:
        age = item.get("age_minutes")
        if age is not None and age > _NEWS_RANKING_MAX_AGE_MINUTES:
            if excluded_reasons is not None:
                excluded_reasons[f"뉴스 랭킹 나이 상한({_NEWS_RANKING_MAX_AGE_MINUTES}분) 초과"] += 1
            continue
        if age is None:
            item["demotion_reason"] = "게시 시각 미상 — lane 하단 강등"
            if excluded_reasons is not None:
                excluded_reasons["시각 미상 강등"] += 1
            demoted.append(item)
        else:
            fresh.append(item)
    return [*fresh, *demoted], len(demoted)


# 0099: lane 사이 우선순위 — 같은 URL/정규제목이 여러 lane에 올라오면 강한 근거가
# 이긴다. 직접 원문(속보) > 최신 뉴스 > 오늘 이슈 > X 네이티브 순서다.
def _dedupe_items_across_lanes(
    lane_lists: list[tuple[str, list[dict[str, Any]]]],
    *,
    dropped: Counter[str] | None = None,
) -> set[int]:
    """우선순위 순으로 훑으며 URL·정규제목 중복 뒤쪽 사본을 버린다.

    반환값은 살아남은 항목의 id() 집합이다(항목 객체 정체성으로 판정). 사본이
    버려질 때마다 dropped에 «URL 중복(lane명)»·«정규제목 중복(lane명)»으로 센다.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    survivors: set[int] = set()
    for lane_name, lane_items in lane_lists:
        for item in lane_items:
            url = str(item.get("source_url") or "").strip()
            title_key = _normalize_keyword(str(item.get("keyword") or ""))
            duplicate = False
            if url:
                if url in seen_urls:
                    if dropped is not None:
                        dropped[f"URL 중복({lane_name})"] += 1
                    duplicate = True
                else:
                    seen_urls.add(url)
            if title_key:
                if title_key in seen_titles:
                    if dropped is not None:
                        dropped[f"정규제목 중복({lane_name})"] += 1
                    duplicate = True
                else:
                    seen_titles.add(title_key)
            if not duplicate:
                survivors.add(id(item))
    return survivors


def _reddit_items(
    raw_items: list[dict[str, Any]],
    now: datetime,
    *,
    filter_shadow_store: FilterShadowStore | None = None,
    excluded_reasons: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    """Reddit 핫 포스트를 점수 없는 후보로 정규화한다.

    시각은 created_utc로부터 source_published_at으로 변환하고(모르면 unknown),
    첨부 형태(video/image/text/unknown, video_url)를 실어 보낸다.
    점수로 환산하지 않고 추천수·댓글수를 사실 필드로 유지한다(0053 규약).
    """
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_items:
        title = str(raw.get("title") or raw.get("keyword") or "").strip()
        url = str(raw.get("url") or raw.get("source_url") or "").strip()
        item_id = str(raw.get("id") or "").strip()
        if not title:
            continue
        if not item_id:
            item_id = hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:16]
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        # 0079: 한국어 계정에 쓸 수 있는가를 스스로 판정하지 않고, 후보로 올리되 언어 필드로만 표시.
        reason = excluded_topic_reason(title)
        record_filter_candidate_fail_open(
            filter_shadow_store,
            source="x-radar",
            candidate_id=item_id,
            title=title,
            extra_text=f"Reddit {raw.get('subreddit') or ''}".strip(),
            filter_verdict="block" if reason else "allow",
            filter_reason=reason or "",
            observed_at=now,
        )
        if reason:
            if excluded_reasons is not None:
                excluded_reasons[reason] += 1
            continue

        observed_at = now.astimezone(UTC).isoformat()
        source_published = _timestamp(raw.get("source_published_at") or raw.get("published_at"))
        source_published_at = source_published.isoformat() if source_published is not None else None
        first_seen_at = str(raw.get("first_seen_at") or "").strip() or None
        age_minutes, age_basis, age_display = _age_fields(
            source_published_at=source_published,
            first_seen_at=first_seen_at,
            now=now,
        )

        subreddit = str(raw.get("subreddit") or "").strip()
        source = str(raw.get("source") or (f"Reddit (r/{subreddit})" if subreddit else "Reddit"))
        publisher = str(raw.get("publisher") or (f"r/{subreddit}" if subreddit else "Reddit"))
        attachment_kind = str(raw.get("attachment_kind") or "unknown")
        video_url = str(raw.get("video_url") or "")
        votes = int(raw.get("votes") or 0)
        comments = int(raw.get("comments") or 0)
        is_korean = bool(raw.get("is_korean") if raw.get("is_korean") is not None else _has_hangul(title))
        language = str(raw.get("language") or ("ko" if is_korean else "en"))

        reasons = list(raw.get("reasons") or [])
        if not reasons:
            reasons = [
                f"r/{subreddit} {votes}upvotes · 댓글 {comments}개"
                if subreddit
                else f"Reddit {votes}upvotes · 댓글 {comments}개"
            ]
            if attachment_kind == "video":
                reasons.append("동영상 첨부")
            elif attachment_kind == "image":
                reasons.append("이미지 첨부")

        item = {
            "id": item_id,
            "keyword": title,
            "title": title,
            "lane": "Reddit 핫 포스트",
            "category": "해외 바이럴",
            "qualification_mode": "reddit_hot_post",
            "context_level": "source_direct",
            "materiality_pass": True,
            "observed_at": observed_at,
            "source": source,
            "publisher": publisher,
            "sources": [source],
            "subreddit": subreddit,
            "author": str(raw.get("author") or ""),
            "votes": votes,
            "comments": comments,
            "source_published_at": source_published_at,
            "first_seen_at": first_seen_at,
            "age_minutes": age_minutes,
            "age_basis": age_basis,
            "age_display": age_display,
            "source_url": url,
            "permalink": str(raw.get("permalink") or ""),
            "attachment_kind": attachment_kind,
            "video_url": video_url,
            "language": language,
            "is_korean": is_korean,
            "volume": "N/A",
            "volume_numeric": 0,
            "news_headlines": [title],
            "news_items": [],
            "first_report": None,
            "threads_posts": [],
            "threads_author_count": 0,
            "x_signal_keywords": [],
            "x_search_url": "",
            "reasons": reasons,
        }
        items.append(item)
    return items


def _attach_x_signals_to_rankings(
    x_trends: list[RawTrend],
    target_items: list[dict[str, Any]],
    *,
    spam_reason_by_rank: dict[int, str] | None = None,
) -> set[int]:
    """같은 사건의 X 트렌드 단어를 랭킹 문장에 「X에서도 뜨고 있음」으로 묶는다.

    매칭은 제목 대비 단어 일치율 0.55 이상(기존 원문 정합 규칙과 동일)이며
    한 단어는 최상위 랭킹 항목 하나에만 붙는다. 매칭된 X 단어의 인덱스를
    돌려줘 후보 구성에서 제외한다.
    """
    matched_ranks: set[int] = set()
    for x_rank, trend in enumerate(x_trends):
        for item in target_items:
            if _title_keyword_relevance(trend.name, str(item.get("keyword") or "")) >= 0.55:
                signals = item.setdefault("x_signal_keywords", [])
                signal: dict[str, Any] = {"keyword": trend.name, "x_rank": x_rank}
                spam_reason = (spam_reason_by_rank or {}).get(x_rank)
                if spam_reason:
                    signal["spam_likely_reason"] = spam_reason
                signals.append(signal)
                item["sources"].append("공개 X 트렌드")
                item["reasons"].append(f"X에서도 뜨고 있음: {trend.name}({x_rank + 1}위)")
                item["x_search_url"] = f"https://x.com/search?q={quote(trend.name)}&src=typed_query&f=live"
                matched_ranks.add(x_rank)
                break
    return matched_ranks


def _freshness_points(age_minutes: int | None, *, x_native: bool) -> int:
    if age_minutes is None:
        return 26 if x_native else 8
    if age_minutes <= 30:
        return 30
    if age_minutes <= 60:
        return 28
    if age_minutes <= 180:
        return 22
    if age_minutes <= 360:
        return 15
    if age_minutes <= 1440:
        return 8
    return 2


def _volume_points(volume: int) -> int:
    if volume <= 0:
        return 0
    return min(25, round(math.log10(volume + 1) / math.log10(100_001) * 25))


def _topic_category(keyword: str, headlines: list[str]) -> str:
    haystack = " ".join([keyword, *headlines]).casefold()
    for category, terms in _CATEGORY_TERMS.items():
        if any(term.casefold() in haystack for term in terms):
            return category
    return "실시간 이슈"


def _is_focus_match(keyword: str, headlines: list[str], focus_keywords: list[str]) -> bool:
    if not focus_keywords:
        return False
    haystack = " ".join([keyword, *headlines]).casefold()
    return any(term.casefold() in haystack for term in focus_keywords)


def _similar_key(keyword: str, existing: dict[str, dict[str, Any]]) -> str | None:
    normalized = _normalize_keyword(keyword)
    if normalized in existing:
        return normalized
    if len(normalized) < 3:
        return None
    for key in existing:
        if len(key) >= 3 and (normalized in key or key in normalized):
            return key
    return None


def _valid_news_items(news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_source_titles: set[tuple[str, str]] = set()
    for item in news_items:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        source = str(item.get("source") or urlparse(url).netloc).strip()
        domain = urlparse(url).netloc.casefold().removeprefix("www.")
        title_key = _normalize_keyword(title)
        source_title = (source.casefold(), title_key)
        if (
            not title
            or url in seen_urls
            or source_title in seen_source_titles
            or urlparse(url).scheme not in {"http", "https"}
            or any(domain == blocked or domain.endswith(f".{blocked}") for blocked in _NEWS_AGGREGATOR_DOMAINS)
            or source.casefold() in _NEWS_AGGREGATOR_SOURCES
            or excluded_topic_reason(title, source)
        ):
            continue
        seen_urls.add(url)
        seen_source_titles.add(source_title)
        normalized = {"title": title, "url": url, "source": source}
        if item.get("published_at"):
            normalized["published_at"] = str(item["published_at"])
        if item.get("discovered_via"):
            normalized["discovered_via"] = str(item["discovered_via"])
        valid.append(normalized)
    return valid


def _news_timestamp(item: dict[str, Any]) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(item.get("published_at") or ""))
    except ValueError:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)


def _merge_news_items(
    trend_items: list[dict[str, Any]],
    expanded_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = _valid_news_items([*trend_items, *expanded_items])
    items.sort(
        key=lambda item: (_news_timestamp(item) is None, _news_timestamp(item) or datetime.max.replace(tzinfo=UTC))
    )
    timestamped = [item for item in items if _news_timestamp(item) is not None]
    if timestamped:
        timestamped[0]["is_first_report"] = True
        timestamped[0]["first_report_scope"] = "수집 원문 중 최초"
    return items


def _independent_source_count(news_items: list[dict[str, Any]]) -> int:
    sources = {
        (item.get("source") or urlparse(item["url"]).netloc).strip().casefold()
        for item in news_items
        if item.get("url")
    }
    return len(sources)


def _title_keyword_relevance(keyword: str, title: str) -> float:
    keyword_key = _normalize_keyword(keyword)
    title_key = _normalize_keyword(title)
    if not keyword_key or not title_key:
        return 0.0
    if keyword_key in title_key:
        return 1.0
    tokens = [token for token in re.findall(r"[0-9a-z가-힣]{2,}", keyword.casefold()) if len(token) >= 2]
    if len(tokens) > 1:
        matched = sum(1 for token in tokens if _normalize_keyword(token) in title_key)
        return matched / len(tokens)
    if len(keyword_key) < 5:
        return 0.0
    minimum = max(3, math.ceil(len(keyword_key) * 0.55))
    for size in range(len(keyword_key) - 1, minimum - 1, -1):
        if any(keyword_key[start : start + size] in title_key for start in range(len(keyword_key) - size + 1)):
            return size / len(keyword_key)
    return 0.0


def _coherent_news_items(keyword: str, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """한국어 시장 후보의 교차 확인은 한국어 기사로만 한다(0071 반증 «elle»).

    한국어 트렌드 «elle»가 프랑스어 대명사로 프랑스어 기사 3건에 매칭돼
    verified가 됐다. 이 레이더의 후보는 전부 한국 시장 키워드이므로 교차
    확인에 세는 기사 제목에는 한글이 있어야 한다. discovered_via 우대
    경로(트렌드 첨부 원문)도 같은 언어 검사를 통과해야 한다.
    """
    return [
        item
        for item in news_items
        if _has_hangul(str(item.get("title") or ""))
        and (not item.get("discovered_via") or _title_keyword_relevance(keyword, str(item.get("title") or "")) >= 0.55)
    ]


def _recent_news_count(news_items: list[dict[str, Any]], now: datetime, *, hours: int = 6) -> int:
    cutoff_seconds = hours * 60 * 60
    count = 0
    for item in news_items:
        published = _news_timestamp(item)
        if published is None:
            continue
        age_seconds = (now - published).total_seconds()
        if 0 <= age_seconds <= cutoff_seconds:
            count += 1
    return count


def _threads_author_count(threads_posts: list[dict[str, Any]]) -> int:
    return len({str(post.get("username") or "").strip().casefold() for post in threads_posts if post.get("username")})


def _materiality_assessment(
    candidate: dict[str, Any],
    focus_keywords: list[str],
    news_items: list[dict[str, Any]],
    threads_posts: list[dict[str, Any]],
) -> tuple[int, list[str], bool, str]:
    google: RawTrend | None = candidate.get("google")
    x_trend: RawTrend | None = candidate.get("x")
    headlines = list((google.extra or {}).get("news_headlines", [])) if google else []
    volume = google.volume_numeric if google else 0
    age_minutes = candidate.get("age_minutes")
    coherent_news = _coherent_news_items(candidate["keyword"], news_items)
    source_count = _independent_source_count(coherent_news)
    title_match_count = sum(
        1 for item in news_items if _title_keyword_relevance(candidate["keyword"], str(item.get("title") or "")) >= 0.55
    )
    threads_authors = _threads_author_count(threads_posts)
    evidence_score = min(
        40,
        source_count * 15 + (10 if source_count >= 3 else 0) + min(15, threads_authors * 5),
    )
    freshness_score = round(_freshness_points(age_minutes, x_native=x_trend is not None) * 0.8)
    volume_score = round(_volume_points(volume) * 0.8)
    x_rank = candidate.get("x_rank")
    x_signal = max(5, 12 - int(x_rank * 0.5)) if x_rank is not None else 0
    focus_signal = 5 if _is_focus_match(candidate["keyword"], headlines, focus_keywords) else 0
    score = min(100, evidence_score + freshness_score + volume_score + x_signal)

    has_news_evidence = source_count >= 2
    has_mixed_evidence = source_count >= 1 and threads_authors >= 2
    has_cross_social_evidence = bool(x_trend) and threads_authors >= 3
    if not (has_news_evidence or has_mixed_evidence or has_cross_social_evidence):
        gate_reason = "주제 일치 원문·Threads 교차 근거 부족"
    elif has_news_evidence and title_match_count == 0 and threads_authors == 0:
        gate_reason = "주제와 원문 제목 불일치"
    elif age_minutes is not None and age_minutes > 1440:
        gate_reason = "급등 시점 24시간 경과"
    else:
        gate_reason = ""
    materiality_pass = not gate_reason

    reasons: list[str] = []
    if source_count:
        reasons.append(f"독립 원문 {source_count}곳")
    if threads_authors:
        reasons.append(f"Threads 최근 작성자 {threads_authors}명")
    if age_minutes is not None:
        reasons.append(f"{age_minutes}분 전 검색 급등")
    if volume:
        reasons.append(f"검색량 약 {volume:,}+")
    if x_rank is not None:
        reasons.append(f"공개 X 트렌드 {x_rank + 1}위 교차 신호")
    if google and x_trend:
        reasons.append("검색·X 동시 반응")
    if focus_signal:
        reasons.append("관심 키워드 일치")
    return score, reasons, materiality_pass, gate_reason


def _x_exposure_assessment(
    candidate: dict[str, Any],
    news_items: list[dict[str, Any]],
    threads_posts: list[dict[str, Any]],
    now: datetime,
    observation: dict[str, Any] | None = None,
) -> tuple[int, dict[str, int], list[str], str, float]:
    google: RawTrend | None = candidate.get("google")
    x_trend: RawTrend | None = candidate.get("x")
    keyword = candidate["keyword"]
    coherent_news = _coherent_news_items(keyword, news_items)
    coherent_sources = _independent_source_count(coherent_news)
    recent_news = _recent_news_count(coherent_news, now, hours=6)
    threads_authors = _threads_author_count(threads_posts)
    age_minutes = candidate.get("age_minutes")

    recency = 0 if age_minutes is None else max(2, round(25 * math.exp(-max(0, age_minutes) / 360)))

    x_rank = candidate.get("x_rank")
    if x_rank is not None:
        x_momentum = max(3, 20 - int(x_rank))
    else:
        volume = google.volume_numeric if google else 0
        x_momentum = min(10, round(_volume_points(volume) * 0.4))

    source_velocity = min(12, coherent_sources * 4) + min(8, recent_news * 2)
    cross_platform = (7 if google and x_trend else 0) + min(8, threads_authors * 3)
    relevance_values = [_title_keyword_relevance(keyword, str(item.get("title") or "")) for item in news_items[:8]]
    clarity = round(10 * (sum(relevance_values) / len(relevance_values))) if relevance_values else 0
    observed = observation or {}
    observed_growth = min(
        10,
        max(0, int(observed.get("new_sources") or 0)) * 3
        + max(0, int(observed.get("new_originals") or 0)) * 2
        + max(0, int(observed.get("x_rank_change") or 0)) * 2,
    )
    breakdown = {
        "recency": recency,
        "x_momentum": x_momentum,
        "source_velocity": source_velocity,
        "cross_platform": cross_platform,
        "topic_clarity": clarity,
        "observed_growth": observed_growth,
    }
    if age_minutes is None:
        confidence = "low"
        coverage = 0.75
    elif coherent_sources >= 2 and (x_rank is not None or recent_news > 0):
        confidence = "high"
        coverage = 1.0
    else:
        confidence = "medium"
        coverage = 0.9
    score = min(100, round(sum(breakdown.values()) * coverage))
    signals = [
        f"주제 일치 원문 {len(coherent_news)}/{len(news_items)}건",
        f"최근 6시간 원문 {recent_news}건",
        f"시간 감쇠 {recency}/25" if age_minutes is not None else "급등 시각 미확인 · 시간 점수 0",
    ]
    if x_rank is not None:
        signals.append(f"공개 X 트렌드 {x_rank + 1}위")
    if threads_authors:
        signals.append(f"Threads 작성자 {threads_authors}명")
    if observed.get("previous_observed_at"):
        signals.append(
            "직전 관측 대비 "
            f"새 원문 +{int(observed.get('new_originals') or 0)} · "
            f"새 출처 +{int(observed.get('new_sources') or 0)}"
        )
        rank_change = observed.get("x_rank_change")
        if isinstance(rank_change, int) and rank_change:
            signals.append(f"공개 X 순위 {abs(rank_change)}계단 {'상승' if rank_change > 0 else '하락'}")
    else:
        signals.append("첫 관측 · 증가량은 다음 갱신부터 계산")
    return score, breakdown, signals, confidence, coverage


def _x_native_assessment(
    candidate: dict[str, Any],
    threads_posts: list[dict[str, Any]],
    observation: dict[str, Any],
) -> tuple[int, dict[str, int], list[str], str, float]:
    x_rank = int(candidate.get("x_rank") or 0)
    rank_signal = max(8, 40 - x_rank * 3)
    rank_change = max(0, int(observation.get("x_rank_change") or 0))
    streak = max(0, int(observation.get("positive_rank_streak") or 0))
    observation_count = max(1, int(observation.get("observation_count") or 1))
    acceleration = min(25, rank_change * 4 + streak * 6)
    persistence = min(15, observation_count * 2)
    threads_authors = _threads_author_count(threads_posts)
    cross_social = min(20, threads_authors * 5)
    breakdown = {
        "public_x_rank": rank_signal,
        "rank_acceleration": acceleration,
        "repeated_observation": persistence,
        "threads_authors": cross_social,
    }
    confidence = "medium" if threads_authors >= 2 else "low"
    coverage = 0.9 if confidence == "medium" else 0.75
    score = min(75, round(sum(breakdown.values()) * coverage))
    signals = [f"공개 X 트렌드 {x_rank + 1}위"]
    if observation.get("sample_advanced") is False:
        signals.append("90초 캐시 재표시 · 반복 관측에 미포함")
    else:
        signals.append(f"짧은 간격 반복 관측 {observation_count}회")
    signals.append("뉴스 맥락 미확인 · X 네이티브 저신뢰도")
    if rank_change:
        signals.append(f"직전 관측 대비 {rank_change}계단 상승")
    if streak >= 2:
        signals.append(f"연속 순위 상승 {streak}회")
    if threads_authors:
        signals.append(f"Threads 작성자 {threads_authors}명")
    return score, breakdown, signals, confidence, coverage


def _x_native_gate(
    candidate: dict[str, Any],
    observation: dict[str, Any],
    now: datetime,
) -> bool:
    keyword = str(candidate.get("keyword") or "").strip()
    x_rank = candidate.get("x_rank")
    if not candidate.get("x") or not isinstance(x_rank, int) or not (2 <= len(keyword) <= 60):
        return False
    if observation.get("sample_advanced") is not True:
        return False
    try:
        previous_at = datetime.fromisoformat(str(observation.get("previous_observed_at"))).astimezone(UTC)
    except (TypeError, ValueError):
        return False
    recently_repeated = 0 <= (now - previous_at).total_seconds() <= 5 * 60
    if not recently_repeated:
        return False
    observation_count = int(observation.get("observation_count") or 0)
    positive_rank_streak = int(observation.get("positive_rank_streak") or 0)
    top_five_persisted = x_rank <= 4 and observation_count >= 2
    sustained_acceleration = x_rank <= 14 and positive_rank_streak >= 2
    return top_five_persisted or sustained_acceleration


def _lane(candidate: dict[str, Any]) -> str:
    if candidate.get("google") and candidate.get("x"):
        return "동시 폭발"
    if candidate.get("google"):
        return "속보·검색 급등"
    return "X 바이럴"


class XOpportunityRadar:
    """Fuse Google Trending Now and public Korean X trend signals."""

    def __init__(
        self,
        google_fetcher: TrendFetcher = _async_fetch_google_trends_rss,
        x_fetcher: TrendFetcher = _async_fetch_getdaytrends,
        threads_collector: ThreadsSignalCollector | None = None,
        news_fetcher: NewsFetcher | None = fetch_bing_news_origins,
        news_ranking_fetcher: RankingFetcher | None = None,
        daum_realtime_fetcher: DaumFetcher | None = None,
        reddit_fetcher: RedditFetcher | None = None,
        observation_path: Path | None = None,
        filter_shadow_store: FilterShadowStore | None = None,
        breaking_news_observer: BreakingNewsObserver | None = None,
    ):
        self.google_fetcher = google_fetcher
        self.x_fetcher = x_fetcher
        self.threads_collector = threads_collector or ThreadsSignalCollector()
        self.news_fetcher = news_fetcher
        self.news_ranking_fetcher = news_ranking_fetcher
        self.daum_realtime_fetcher = daum_realtime_fetcher
        self.reddit_fetcher = reddit_fetcher
        self.exposure_tracker = ExposureObservationTracker(observation_path)
        self.filter_shadow_store = filter_shadow_store
        self.breaking_news_observer: BreakingNewsObserver | None
        if breaking_news_observer is not None:
            self.breaking_news_observer = breaking_news_observer
        elif (
            filter_shadow_store is not None
            and google_fetcher is _async_fetch_google_trends_rss
            and x_fetcher is _async_fetch_getdaytrends
        ):
            self.breaking_news_observer = BreakingNewsObserver(filter_shadow_store)
        else:
            # Unit/custom fetchers remain hermetic unless the observer is
            # explicitly injected.  The dashboard uses both production
            # fetchers and therefore enables this lane automatically.
            self.breaking_news_observer = None
        self._refresh_lock = asyncio.Lock()
        self._snapshot: dict[str, Any] = {
            "available": False,
            "items": [],
            "refreshed_at": None,
            "last_attempt_at": None,
            "last_success_at": None,
            "is_stale": False,
            "serving_last_good": False,
            "source_health": {
                "google_trends": False,
                "public_x_trends": False,
                "daum_realtime": False,
                "news_rankings": False,
                "reddit": False,
                "threads_api": self.threads_collector.available,
                "publisher_news_origins": False,
                "google_news_rss": False,
                "yonhap_rss": False,
                "kma_weather": False,
            },
            "breaking_news_observation": {"enabled": self.breaking_news_observer is not None},
            "news_ranking_count": 0,
            "news_ranking_raw_count": 0,
            "news_ranking_filter_summary": {},
            "news_ranking_demoted_count": 0,
            "breaking_now_items": [],
            "breaking_now_count": 0,
            "latest_news_items": [],
            "latest_news_count": 0,
            "today_issue_items": [],
            "today_issue_count": 0,
            "x_native_items": [],
            "breaking_filter_summary": {},
            "cross_lane_dedupe_count": 0,
            "cross_lane_dedupe_summary": {},
            "daum_trend_count": 0,
            "daum_raw_count": 0,
            "daum_updated_at": None,
            "daum_trend_filter_summary": {},
            "reddit_count": 0,
            "reddit_raw_count": 0,
            "reddit_filter_summary": {},
            "observed_only_count": 0,
            "observed_only_items": [],
            "spam_flagged_count": 0,
            "spam_flagged_items": [],
            "errors": [],
        }

    def snapshot(self) -> dict[str, Any]:
        return dict(self._snapshot)

    async def refresh(
        self,
        *,
        country: str = "korea",
        limit: int = 20,
        focus_keywords: list[str] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        focus = [value.strip() for value in (focus_keywords or []) if value.strip()][:8]
        limit = min(30, max(5, int(limit)))

        async with self._refresh_lock:
            previous_snapshot = self.snapshot()
            async with httpx.AsyncClient(follow_redirects=True) as session:
                is_production_fetchers = (
                    self.google_fetcher is _async_fetch_google_trends_rss
                    and self.x_fetcher is _async_fetch_getdaytrends
                )
                ranking_fetcher = self.news_ranking_fetcher
                daum_fetcher = self.daum_realtime_fetcher
                reddit_fetcher = self.reddit_fetcher
                if is_production_fetchers and ranking_fetcher is None:
                    # 대시보드는 두 생산 fetcher를 쓰므로 랭킹 lane을 자동으로 켠다.
                    # 단위 테스트의 커스텀 fetcher 세션은 자동으로 꺼져 hermetical을 유지한다.
                    ranking_fetcher = _async_fetch_news_rankings
                if is_production_fetchers and daum_fetcher is None:
                    # 1순위 소스도 같은 생산 조건에서 자동으로 켠다.
                    daum_fetcher = _async_fetch_daum_realtime
                if is_production_fetchers and reddit_fetcher is None:
                    # Reddit 핫 포스트도 같은 생산 조건에서 자동으로 켠다.
                    reddit_fetcher = _async_fetch_reddit_hot
                if self.x_fetcher is _async_fetch_getdaytrends:
                    x_request = self.x_fetcher(
                        session,
                        country,
                        max(limit, 20),
                        force_refresh=force_refresh,
                    )
                else:
                    x_request = self.x_fetcher(session, country, max(limit, 20))
                gather_tasks: list[Awaitable[object]] = [
                    self.google_fetcher(session, country, max(limit, 20)),
                    x_request,
                ]
                result_index: dict[str, int | None] = {"ranking": None, "daum": None, "reddit": None}
                if ranking_fetcher is not None:
                    result_index["ranking"] = len(gather_tasks)
                    gather_tasks.append(ranking_fetcher(session, max(limit, 20)))
                if daum_fetcher is not None:
                    result_index["daum"] = len(gather_tasks)
                    gather_tasks.append(daum_fetcher(session, max(limit, 20)))
                if reddit_fetcher is not None:
                    result_index["reddit"] = len(gather_tasks)
                    gather_tasks.append(reddit_fetcher(session, max(limit, 20)))
                gathered = await asyncio.gather(*gather_tasks, return_exceptions=True)
                google_result, x_result = gathered[0], gathered[1]
                ranking_result = gathered[result_index["ranking"]] if result_index["ranking"] is not None else []
                daum_result = gathered[result_index["daum"]] if result_index["daum"] is not None else (None, [])
                reddit_result = gathered[result_index["reddit"]] if result_index["reddit"] is not None else []

            errors: list[str] = []
            google_trends: list[RawTrend] = []
            x_trends: list[RawTrend] = []
            x_fallback_count = 0
            ranking_raw: list[dict[str, Any]] = []
            daum_updated_at: str | None = None
            daum_raw: list[dict[str, Any]] = []
            reddit_raw: list[dict[str, Any]] = []
            if isinstance(google_result, Exception):
                errors.append(f"Google Trends: {str(google_result)[:180]}")
            else:
                google_trends = list(google_result)
            if isinstance(ranking_result, Exception):
                errors.append(f"뉴스 랭킹 수집: {str(ranking_result)[:180]}")
            elif ranking_fetcher is not None:
                ranking_raw = [item for item in ranking_result if isinstance(item, dict)]
            if isinstance(daum_result, Exception):
                errors.append(f"다음 실시간 트렌드: {str(daum_result)[:180]}")
            elif daum_fetcher is not None:
                if isinstance(daum_result, tuple) and len(daum_result) == 2:
                    daum_updated_at, daum_raw = daum_result
                elif isinstance(daum_result, list):
                    daum_raw = daum_result
            if isinstance(reddit_result, Exception):
                errors.append(f"Reddit 핫 포스트 수집: {str(reddit_result)[:180]}")
            elif reddit_fetcher is not None:
                reddit_raw = [item for item in reddit_result if isinstance(item, dict)]
            if isinstance(x_result, Exception):
                errors.append(f"공개 X 트렌드: {str(x_result)[:180]}")
            else:
                x_trends = [
                    item
                    for item in x_result
                    if item.name not in _FALLBACK_X_TOPICS and item.link.startswith("https://getdaytrends.com/")
                ]
                # 0072: fallback은 이름 목록 우연 일치가 아니라 표식으로 감지한다.
                # `_FALLBACK_X_TOPICS`는 sources.py의 `_fallback_trends()`와 다른
                # 파일·레인이 관리해 내용이 어긋나도 조용히 지나쳐 왔다.
                x_fallback_count = sum(
                    1
                    for item in x_result
                    if (item.extra or {}).get("_is_fallback") or (item.extra or {}).get("is_fallback")
                )

            # 교차 확인(3번 강등)이 스팸의 1차 방어선이다. 패턴은 보조 —
            # 목록을 추격하지 않고, 판정된 단어에 라벨만 달아둔다.
            spam_flagged: list[dict[str, Any]] = []
            spam_reason_by_rank: dict[int, str] = {}
            for x_rank, trend in enumerate(x_trends):
                reason = _spam_trend_reason(trend.name)
                if reason:
                    spam_flagged.append({"keyword": trend.name, "x_rank": x_rank, "reason": reason})
                    spam_reason_by_rank[x_rank] = reason

            now = _utc_now()
            daum_excluded_reasons: Counter[str] = Counter()
            daum_items = _daum_trend_items(
                daum_raw,
                now,
                filter_shadow_store=self.filter_shadow_store,
                excluded_reasons=daum_excluded_reasons,
            )
            ranking_excluded_reasons: Counter[str] = Counter()
            ranking_items = _news_ranking_items(
                ranking_raw,
                now,
                filter_shadow_store=self.filter_shadow_store,
                excluded_reasons=ranking_excluded_reasons,
            )
            # 0099: 나이 상한(360분)과 시각 미상 강등은 정규화 뒤 정책 계층에서.
            ranking_items, news_ranking_demoted_count = _apply_news_ranking_freshness_policy(
                ranking_items,
                excluded_reasons=ranking_excluded_reasons,
            )
            matched_x_ranks = _attach_x_signals_to_rankings(
                x_trends,
                [*daum_items, *ranking_items],
                spam_reason_by_rank=spam_reason_by_rank,
            )
            x_sample_id = next(
                (
                    str((trend.extra or {}).get("_getdaytrends_sample_id") or "")
                    for trend in x_trends
                    if (trend.extra or {}).get("_getdaytrends_sample_id")
                ),
                "",
            )
            if x_trends and not x_sample_id and self.x_fetcher is not _async_fetch_getdaytrends:
                x_sample_id = f"custom:{now.isoformat()}"
            candidates: dict[str, dict[str, Any]] = {}
            for trend in google_trends:
                key = _normalize_keyword(trend.name)
                if not key:
                    continue
                candidates[key] = {
                    "keyword": trend.name,
                    "google": trend,
                    "x": None,
                    "x_rank": None,
                    "age_minutes": _age_minutes(trend.published_at, now),
                }
            for rank, trend in enumerate(x_trends):
                if rank in matched_x_ranks:
                    continue
                key = _similar_key(trend.name, candidates) or _normalize_keyword(trend.name)
                if not key:
                    continue
                candidate = candidates.setdefault(
                    key,
                    {
                        "keyword": trend.name,
                        "google": None,
                        "x": None,
                        "x_rank": None,
                        "age_minutes": None,
                    },
                )
                candidate["x"] = trend
                candidate["x_rank"] = rank

            breaking_news_observation: dict[str, Any] = {
                "enabled": self.breaking_news_observer is not None,
                "available": False,
                "sources": {},
            }
            breaking_product_candidates: object = []
            if self.breaking_news_observer is not None:
                try:
                    breaking_news_observation = await self.breaking_news_observer.observe(
                        (candidate["keyword"] for candidate in candidates.values()),
                        observed_at=now,
                    )
                    breaking_product_candidates = breaking_news_observation.pop("product_candidates", [])
                except Exception:
                    # The additive lane must never affect the existing radar
                    # response path when its observer fails.
                    errors.append("L0/L1 shadow 관찰 실패")
            breaking_excluded_reasons: Counter[str] = Counter()
            breaking_items = _breaking_lane_items(
                breaking_product_candidates,
                now,
                limit=limit,
                excluded_reasons=breaking_excluded_reasons,
            )

            for candidate in candidates.values():
                google = candidate.get("google")
                headlines = list((google.extra or {}).get("news_headlines", [])) if google else []
                candidate["excluded_topic_reason"] = excluded_topic_reason(candidate["keyword"], *headlines)
                keyword = candidate["keyword"]
                record_filter_candidate_fail_open(
                    self.filter_shadow_store,
                    source="x-radar",
                    candidate_id=hashlib.sha256(keyword.casefold().encode("utf-8")).hexdigest()[:16],
                    title=keyword,
                    extra_text=" ".join(headlines),
                    filter_verdict="block" if candidate["excluded_topic_reason"] else "allow",
                    filter_reason=candidate["excluded_topic_reason"] or "",
                    observed_at=now,
                )

            eligible_candidates = [
                candidate for candidate in candidates.values() if not candidate.get("excluded_topic_reason")
            ]
            google_candidates = [candidate for candidate in eligible_candidates if candidate.get("google")][:8]
            x_only_candidates = [
                candidate for candidate in eligible_candidates if candidate.get("x") and not candidate.get("google")
            ][:5]
            threads_targets = google_candidates + x_only_candidates
            if self.threads_collector.available and threads_targets:
                semaphore = asyncio.Semaphore(4)

                async def fetch_threads(candidate: dict[str, Any]):
                    async with semaphore:
                        return await self.threads_collector.search(session, candidate["keyword"], limit=5)

                async with httpx.AsyncClient(follow_redirects=True) as session:
                    threads_results = await asyncio.gather(
                        *(fetch_threads(candidate) for candidate in threads_targets),
                        return_exceptions=True,
                    )
                thread_errors = 0
                for candidate, result in zip(threads_targets, threads_results, strict=True):
                    if isinstance(result, Exception):
                        thread_errors += 1
                        candidate["threads_posts"] = []
                    else:
                        candidate["threads_posts"] = result
                if thread_errors:
                    errors.append(f"Threads 공식 검색 일부 실패 ({thread_errors}건)")

            news_origin_ok = False
            expanded_news_count = 0
            if self.news_fetcher and google_candidates:
                news_semaphore = asyncio.Semaphore(4)

                async def fetch_news(candidate: dict[str, Any]):
                    async with news_semaphore:
                        return await self.news_fetcher(news_session, candidate["keyword"], 8)

                async with httpx.AsyncClient(follow_redirects=True) as news_session:
                    news_results = await asyncio.gather(
                        *(fetch_news(candidate) for candidate in google_candidates),
                        return_exceptions=True,
                    )
                news_errors = 0
                for candidate, result in zip(google_candidates, news_results, strict=True):
                    if isinstance(result, Exception):
                        news_errors += 1
                        candidate["expanded_news_items"] = []
                    else:
                        candidate["expanded_news_items"] = result
                        expanded_news_count += len(result)
                        news_origin_ok = True
                if news_errors:
                    errors.append(f"게시사 원문 확대 일부 실패 ({news_errors}건)")

            items: list[dict[str, Any]] = []
            observed_only_items: list[dict[str, Any]] = []
            filtered_reasons: Counter[str] = Counter()
            previous_native_keywords = {
                _normalize_keyword(str(item.get("keyword") or ""))
                for item in self._snapshot.get("items", [])
                if item.get("qualification_mode") == "x_native_history"
            }
            previous_native_keywords |= {
                _normalize_keyword(str(item.get("keyword") or ""))
                for item in self._snapshot.get("observed_only_items", [])
            }
            for candidate in candidates.values():
                if candidate.get("excluded_topic_reason"):
                    filtered_reasons[candidate["excluded_topic_reason"]] += 1
                    continue
                google = candidate.get("google")
                x_trend = candidate.get("x")
                keyword = candidate["keyword"]
                headlines = list((google.extra or {}).get("news_headlines", [])) if google else []
                trend_news_items = list((google.extra or {}).get("news_items", [])) if google else []
                news_items = _merge_news_items(trend_news_items, list(candidate.get("expanded_news_items", [])))
                threads_posts = list(candidate.get("threads_posts", []))
                coherent_news = _coherent_news_items(keyword, news_items)
                observation_key = f"x:{_normalize_keyword(keyword)}"
                first_seen_at = _first_seen_at(self.exposure_tracker, observation_key, now)
                observation = self.exposure_tracker.record(
                    observation_key,
                    {
                        "x_rank": candidate.get("x_rank"),
                        "original_count": len(coherent_news),
                        "source_count": _independent_source_count(coherent_news),
                        "threads_authors": _threads_author_count(threads_posts),
                        "volume": google.volume_numeric if google else 0,
                        "sample_id": x_sample_id if x_trend else None,
                        "first_seen_at": first_seen_at,
                    },
                    observed_at=now,
                    score_version=_X_EXPOSURE_SCORE_VERSION,
                )
                source_published_at = _timestamp(google.published_at) if google and google.published_at else None
                age_minutes, age_basis, age_display = _age_fields(
                    source_published_at=source_published_at,
                    first_seen_at=first_seen_at,
                    now=now,
                )
                candidate["age_minutes"] = age_minutes
                candidate["age_basis"] = age_basis
                candidate["first_seen_at"] = first_seen_at
                lane = _lane(candidate)
                score, reasons, materiality_pass, gate_reason = _materiality_assessment(
                    candidate,
                    focus,
                    news_items,
                    threads_posts,
                )
                cached_native_replay = bool(
                    not materiality_pass
                    and observation.get("sample_advanced") is False
                    and _normalize_keyword(keyword) in previous_native_keywords
                )
                x_native_pass = bool(
                    not materiality_pass and (_x_native_gate(candidate, observation, now) or cached_native_replay)
                )
                if not materiality_pass and not x_native_pass:
                    filtered_reasons[gate_reason] += 1
                    continue
                if x_native_pass:
                    (
                        x_exposure_score,
                        exposure_breakdown,
                        exposure_signals,
                        exposure_confidence,
                        exposure_coverage,
                    ) = _x_native_assessment(candidate, threads_posts, observation)
                    lane = "X 네이티브 급등"
                    category = "X 네이티브"
                    score = x_exposure_score
                    reasons = [
                        "90초 캐시에서 직전 검증 결과 재표시"
                        if cached_native_replay
                        else "뉴스 원문 없이 공개 X 순위 이력으로만 통과"
                    ]
                else:
                    (
                        x_exposure_score,
                        exposure_breakdown,
                        exposure_signals,
                        exposure_confidence,
                        exposure_coverage,
                    ) = _x_exposure_assessment(
                        candidate,
                        news_items,
                        threads_posts,
                        now,
                        observation,
                    )
                    category = _topic_category(keyword, headlines)
                encoded = quote(keyword)
                primary_url = next(
                    (str(item.get("url") or "") for item in news_items if item.get("url")),
                    str(threads_posts[0].get("permalink") or "")
                    if threads_posts
                    else (x_trend.link if x_trend else (google.link if google else "")),
                )
                first_report = next((article for article in news_items if article.get("is_first_report")), None)
                item = {
                    "id": hashlib.sha256(keyword.casefold().encode("utf-8")).hexdigest()[:16],
                    "keyword": keyword,
                    "materiality_score": score,
                    "opportunity_score": score,
                    "x_exposure_score": x_exposure_score,
                    "exposure_breakdown": exposure_breakdown,
                    "exposure_signals": exposure_signals,
                    "score_version": _X_EXPOSURE_SCORE_VERSION,
                    "exposure_confidence": exposure_confidence,
                    "exposure_coverage": exposure_coverage,
                    "observed_at": observation["observed_at"],
                    "observation_delta": observation,
                    "materiality_pass": True,
                    "qualification_mode": "x_native_history" if x_native_pass else "cross_source_evidence",
                    "context_level": "low" if x_native_pass else "verified",
                    "lane": lane,
                    "category": category,
                    "volume": google.volume if google else "N/A",
                    "volume_numeric": google.volume_numeric if google else 0,
                    "age_minutes": candidate.get("age_minutes"),
                    "age_basis": candidate["age_basis"],
                    "age_display": age_display,
                    "first_seen_at": candidate["first_seen_at"],
                    "source_published_at": (
                        source_published_at.astimezone(UTC).isoformat() if source_published_at is not None else None
                    ),
                    "sources": [
                        source
                        for source, present in (
                            ("Google Trends", bool(google)),
                            ("공개 X 트렌드", bool(x_trend)),
                            ("Threads", bool(threads_posts)),
                        )
                        if present
                    ],
                    "news_headlines": headlines,
                    "news_items": news_items,
                    "first_report": first_report,
                    "threads_posts": threads_posts,
                    "threads_author_count": _threads_author_count(threads_posts),
                    "reasons": reasons,
                    "published_at": google.published_at.isoformat() if google and google.published_at else None,
                    "source_url": primary_url,
                    "trend_url": google.link if google and google.link else (x_trend.link if x_trend else ""),
                    "x_search_url": f"https://x.com/search?q={encoded}&src=typed_query&f=live",
                    "threads_search_url": f"https://www.threads.com/search?q={encoded}",
                    "news_search_url": f"https://news.google.com/search?q={encoded}&hl=ko&gl=KR&ceid=KR%3Ako",
                }
                if item["context_level"] == "low" and not headlines and not first_report:
                    # 「왜 후보인가」가 없는 항목은 지우지 않고 관측만 칸으로 강등한다.
                    filtered_reasons["맥락 없음 관측만 강등"] += 1
                    observed_only_items.append(
                        {
                            "id": item["id"],
                            "keyword": keyword,
                            "x_rank": candidate.get("x_rank"),
                            "observed_at": item["observed_at"],
                            "context_level": "low",
                            "news_headlines": [],
                            "first_report": None,
                            "demotion_reason": "뉴스 맥락 없음(다음 트렌드·랭킹 문장 매칭 없음, 제목·최초 보도 없음)",
                            "spam_likely_reason": spam_reason_by_rank.get(candidate.get("x_rank")),
                            "trend_url": item["trend_url"],
                            "x_search_url": item["x_search_url"],
                        }
                    )
                    continue
                items.append(item)

            items.sort(
                key=lambda item: (
                    item["x_exposure_score"],
                    item["materiality_score"],
                    item["volume_numeric"],
                ),
                reverse=True,
            )
            legacy_items = items[:limit]
            reddit_excluded_reasons: Counter[str] = Counter()
            reddit_items = _reddit_items(
                reddit_raw,
                now,
                filter_shadow_store=self.filter_shadow_store,
                excluded_reasons=reddit_excluded_reasons,
            )
            # 0099: 근거의 성격별 배열 — 지금 속보 / 최신 뉴스 / 오늘 이슈 / X 네이티브.
            # `items`는 기존 조성 순서를 그대로 유지한다(호환), 새 배열이 소비처다.
            breaking_now_items = [item for item in breaking_items if item.get("urgency") == "urgent"]
            latest_news_items = [item for item in breaking_items if item.get("urgency") == "latest"]
            today_core_items = [*daum_items, *ranking_items, *legacy_items, *reddit_items]
            x_native_items = [
                item for item in today_core_items if item.get("qualification_mode") == "x_native_history"
            ]
            today_issue_items = [
                item for item in today_core_items if item.get("qualification_mode") != "x_native_history"
            ]
            cross_lane_dedupe_summary: Counter[str] = Counter()
            dedupe_survivors = _dedupe_items_across_lanes(
                [
                    ("지금 속보", breaking_now_items),
                    ("최신 뉴스", latest_news_items),
                    ("오늘 이슈", today_issue_items),
                    ("X 네이티브", x_native_items),
                ],
                dropped=cross_lane_dedupe_summary,
            )
            breaking_now_items = [item for item in breaking_now_items if id(item) in dedupe_survivors]
            latest_news_items = [item for item in latest_news_items if id(item) in dedupe_survivors]
            today_issue_items = [item for item in today_issue_items if id(item) in dedupe_survivors]
            x_native_items = [item for item in x_native_items if id(item) in dedupe_survivors]
            visible_items = [
                item
                for item in [*daum_items, *ranking_items, *legacy_items, *breaking_items, *reddit_items]
                if id(item) in dedupe_survivors
            ]
            self.exposure_tracker.save(now=now)
            source_health = {
                "google_trends": bool(google_trends),
                # 0072: 항목 수가 아니라 «원천에서 왔다는 표식이 있는 항목»으로 판정한다.
                # `_getdaytrends_sample_id`는 실제 수집에만 붙고 fallback에는 없으며,
                # 주입 fetcher는 x_sample_id가 custom: 로 지정된다. fallback이 이름을
                # 바꿔 살아남아도 표식이 없으면 false다(fail-closed).
                "public_x_trends": bool(x_trends) and bool(x_sample_id),
                "daum_realtime": bool(daum_items),
                "news_rankings": bool(ranking_items),
                "reddit": bool(reddit_items),
                "threads_api": self.threads_collector.available,
                "publisher_news_origins": news_origin_ok,
            }
            breaking_sources = breaking_news_observation.get("sources")
            if not isinstance(breaking_sources, dict):
                breaking_sources = {}
            for response_key, source_key in (
                ("google_news_rss", "google-news-rss"),
                ("yonhap_rss", "yonhap-rss"),
                ("kma_weather", "kma-weather"),
            ):
                source_status = breaking_sources.get(source_key)
                source_health[response_key] = bool(isinstance(source_status, dict) and source_status.get("available"))
            if not google_trends:
                errors.append("Google Trends 결과 없음")
            # 0072: fallback 발동을 화면·응답에 보이게 한다. 사용자는 로그를 안 본다.
            if x_fallback_count:
                errors.append(
                    f"공개 X 트렌드: 원천 수집 실패로 fallback {x_fallback_count}건이 대체 반환됨(원천 항목 0)"
                )
            if not x_trends:
                errors.append("공개 X 트렌드 결과 없음")
            elif not x_sample_id:
                errors.append("공개 X 트렌드: 원천 표식(_getdaytrends_sample_id) 없는 항목만 감지 — health 미반영")
            if daum_fetcher is not None and not daum_raw:
                errors.append("다음 실시간 트렌드 결과 없음")
            attempt_at = now.isoformat()
            next_snapshot = {
                "available": bool(visible_items),
                "country": country,
                "items": visible_items,
                "total_candidates": len(candidates),
                "news_ranking_count": len(ranking_items),
                "news_ranking_raw_count": len(ranking_raw),
                "news_ranking_filter_summary": dict(ranking_excluded_reasons),
                "news_ranking_demoted_count": news_ranking_demoted_count,
                "daum_trend_count": len(daum_items),
                "daum_raw_count": len(daum_raw),
                "daum_updated_at": daum_updated_at,
                "daum_trend_filter_summary": dict(daum_excluded_reasons),
                "reddit_count": len(reddit_items),
                "reddit_raw_count": len(reddit_raw),
                "reddit_filter_summary": dict(reddit_excluded_reasons),
                "qualified_candidates": len(items),
                "breaking_news_count": len(breaking_items),
                # 0099: 긴급도·근거별 분리 배열. breaking_news_count는 호환을 위해
                # urgent+latest 합계로 유지하고, 세부는 아래 count로 읽는다.
                "breaking_now_items": breaking_now_items,
                "breaking_now_count": len(breaking_now_items),
                "latest_news_items": latest_news_items,
                "latest_news_count": len(latest_news_items),
                "today_issue_items": today_issue_items,
                "today_issue_count": len(today_issue_items),
                "x_native_items": x_native_items,
                "breaking_filter_summary": dict(breaking_excluded_reasons),
                "cross_lane_dedupe_count": sum(cross_lane_dedupe_summary.values()),
                "cross_lane_dedupe_summary": dict(cross_lane_dedupe_summary),
                "filtered_out_count": len(candidates) - len(items),
                "filter_summary": dict(filtered_reasons),
                "strict_materiality": True,
                "x_native_count": len(x_native_items),
                "expanded_news_count": expanded_news_count,
                "observed_only_count": len(observed_only_items),
                "observed_only_items": observed_only_items,
                "spam_flagged_count": len(spam_flagged),
                "spam_flagged_items": spam_flagged,
                "breaking_news_observation": breaking_news_observation,
                "x_cache_ttl_seconds": 90,
                "force_refresh_requested": bool(force_refresh),
                "capabilities": {
                    "threads_keyword_search": {
                        "available": self.threads_collector.available,
                        "mode": "official_api" if self.threads_collector.available else "manual_search_link",
                    }
                },
                "focus_keywords": focus,
                "refreshed_at": attempt_at,
                "last_attempt_at": attempt_at,
                "source_health": source_health,
                "errors": errors,
                "notice": "스포츠·정치·증시·기업 실적·부동산을 제외합니다. 연합뉴스·기상청 직접 원문은 사건·안전·긴급 증거가 있는 것만 «지금 속보»로 올리고 나머지는 «최신 뉴스» lane에 둡니다. 뉴스 랭킹은 게시 360분 상한을 넘으면 걷어내고 게시 시각 미상은 lane 하단으로 강등합니다. 다음 실시간 트렌드(순위 변동 포함)·뉴스 랭킹·Reddit 핫 포스트를 점수 없는 후보로 앞세우고, X 트렌드 단어는 같은 사건의 후보에 「X에서도 뜨고 있음」 신호로 붙입니다. 맥락 없는 X 단어는 관측만 칸으로 강등합니다. 같은 URL·제목이 여러 lane에 올라오면 강한 근거 쪽만 남깁니다.",
            }

            # A successful cycle means at least one collection source actually
            # returned usable source data. Capability flags (for example a
            # configured Threads token) do not count as a successful fetch.
            collection_succeeded = any(
                bool(source_health.get(key))
                for key in (
                    "google_trends",
                    "public_x_trends",
                    "daum_realtime",
                    "news_rankings",
                    "reddit",
                    "publisher_news_origins",
                    "google_news_rss",
                    "yonhap_rss",
                    "kma_weather",
                )
            )
            if collection_succeeded:
                next_snapshot["last_success_at"] = attempt_at
                next_snapshot["is_stale"] = False
                next_snapshot["serving_last_good"] = False
                self._snapshot = next_snapshot
                return self.snapshot()

            last_success_at = previous_snapshot.get("last_success_at") or previous_snapshot.get("refreshed_at")
            if last_success_at:
                # Keep the arrays/counts from the last successful response, but
                # expose diagnostics from this failed attempt.  This prevents a
                # transient all-source outage from blanking the private queue.
                preserved = dict(previous_snapshot)
                preserved.update(
                    {
                        "last_attempt_at": attempt_at,
                        "last_success_at": last_success_at,
                        "is_stale": True,
                        "serving_last_good": True,
                        "source_health": source_health,
                        "errors": errors or ["모든 외부 소스가 결과를 반환하지 않음"],
                        "force_refresh_requested": bool(force_refresh),
                    }
                )
                self._snapshot = preserved
                return self.snapshot()

            next_snapshot["last_success_at"] = None
            next_snapshot["is_stale"] = True
            next_snapshot["serving_last_good"] = False
            if not next_snapshot["errors"]:
                next_snapshot["errors"] = ["모든 외부 소스가 결과를 반환하지 않음"]
            self._snapshot = next_snapshot
            return self.snapshot()
