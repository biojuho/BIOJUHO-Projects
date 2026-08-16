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
    from .collectors.sources import _async_fetch_getdaytrends, _async_fetch_google_trends_rss
    from .content_filters import excluded_topic_reason
    from .exposure_observation_tracker import ExposureObservationTracker
    from .filter_eval.shadow_store import FilterShadowStore, record_filter_candidate_fail_open
    from .models import RawTrend
    from .news_origin_collector import fetch_bing_news_origins
    from .threads_signal_collector import ThreadsSignalCollector
except ImportError:
    from breaking_news_observer import BreakingNewsObserver
    from collectors.sources import _async_fetch_getdaytrends, _async_fetch_google_trends_rss
    from content_filters import excluded_topic_reason
    from exposure_observation_tracker import ExposureObservationTracker
    from filter_eval.shadow_store import FilterShadowStore, record_filter_candidate_fail_open
    from models import RawTrend
    from news_origin_collector import fetch_bing_news_origins
    from threads_signal_collector import ThreadsSignalCollector


TrendFetcher = Callable[[httpx.AsyncClient, str, int], Awaitable[list[RawTrend]]]
NewsFetcher = Callable[[httpx.AsyncClient, str, int], Awaitable[list[dict[str, Any]]]]

_FALLBACK_X_TOPICS = {"주말 계획", "점심 메뉴", "날씨", "커피", "퇴근"}
_X_EXPOSURE_SCORE_VERSION = "x-exposure-v3"
_NEWS_AGGREGATOR_DOMAINS = ("v.daum.net", "news.nate.com", "news.zum.com", "msn.com")
_NEWS_AGGREGATOR_SOURCES = {"daum", "nate", "zum", "msn"}
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


def _breaking_lane_items(raw_candidates: object, now: datetime, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(raw_candidates, list):
        return []
    by_source: dict[str, list[dict[str, Any]]] = {"yonhap-rss": [], "kma": []}
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
        source_label = "연합뉴스" if source == "yonhap-rss" else "기상청"
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
        source_group = "yonhap-rss" if source == "yonhap-rss" else "kma"
        by_source[source_group].append(
            {
                "id": candidate_id,
                "keyword": keyword,
                "lane": "속보·공적발표",
                "category": "공적 발표",
                "qualification_mode": "public_source_breaking",
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
                "reasons": [f"{source_label} 직접 발표 · 기존 점수열과 분리"],
            }
        )
    items: list[dict[str, Any]] = []
    for index in range(max(len(values) for values in by_source.values())):
        for source_group in ("yonhap-rss", "kma"):
            source_items = by_source[source_group]
            if index < len(source_items):
                items.append(source_items[index])
                if len(items) >= limit:
                    return items
    return items


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
    items.sort(key=lambda item: (_news_timestamp(item) is None, _news_timestamp(item) or datetime.max.replace(tzinfo=UTC)))
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
    return [
        item
        for item in news_items
        if not item.get("discovered_via")
        or _title_keyword_relevance(keyword, str(item.get("title") or "")) >= 0.55
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
        1
        for item in news_items
        if _title_keyword_relevance(candidate["keyword"], str(item.get("title") or "")) >= 0.55
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
    relevance_values = [
        _title_keyword_relevance(keyword, str(item.get("title") or "")) for item in news_items[:8]
    ]
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
        observation_path: Path | None = None,
        filter_shadow_store: FilterShadowStore | None = None,
        breaking_news_observer: BreakingNewsObserver | None = None,
    ):
        self.google_fetcher = google_fetcher
        self.x_fetcher = x_fetcher
        self.threads_collector = threads_collector or ThreadsSignalCollector()
        self.news_fetcher = news_fetcher
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
            "source_health": {
                "google_trends": False,
                "public_x_trends": False,
                "threads_api": self.threads_collector.available,
                "publisher_news_origins": False,
                "google_news_rss": False,
                "yonhap_rss": False,
                "kma_weather": False,
            },
            "breaking_news_observation": {"enabled": self.breaking_news_observer is not None},
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
            async with httpx.AsyncClient(follow_redirects=True) as session:
                if self.x_fetcher is _async_fetch_getdaytrends:
                    x_request = self.x_fetcher(
                        session,
                        country,
                        max(limit, 20),
                        force_refresh=force_refresh,
                    )
                else:
                    x_request = self.x_fetcher(session, country, max(limit, 20))
                google_result, x_result = await asyncio.gather(
                    self.google_fetcher(session, country, max(limit, 20)),
                    x_request,
                    return_exceptions=True,
                )

            errors: list[str] = []
            google_trends: list[RawTrend] = []
            x_trends: list[RawTrend] = []
            if isinstance(google_result, Exception):
                errors.append(f"Google Trends: {str(google_result)[:180]}")
            else:
                google_trends = list(google_result)
            if isinstance(x_result, Exception):
                errors.append(f"공개 X 트렌드: {str(x_result)[:180]}")
            else:
                x_trends = [
                    item
                    for item in x_result
                    if item.name not in _FALLBACK_X_TOPICS and item.link.startswith("https://getdaytrends.com/")
                ]

            now = _utc_now()
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
            breaking_items = _breaking_lane_items(breaking_product_candidates, now, limit=limit)

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
            filtered_reasons: Counter[str] = Counter()
            previous_native_keywords = {
                _normalize_keyword(str(item.get("keyword") or ""))
                for item in self._snapshot.get("items", [])
                if item.get("qualification_mode") == "x_native_history"
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
                    not materiality_pass
                    and (_x_native_gate(candidate, observation, now) or cached_native_replay)
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
                items.append(
                    {
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
                            source_published_at.astimezone(UTC).isoformat()
                            if source_published_at is not None
                            else None
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
                )

            items.sort(
                key=lambda item: (
                    item["x_exposure_score"],
                    item["materiality_score"],
                    item["volume_numeric"],
                ),
                reverse=True,
            )
            legacy_items = items[:limit]
            visible_items = [*legacy_items, *breaking_items]
            self.exposure_tracker.save(now=now)
            source_health = {
                "google_trends": bool(google_trends),
                "public_x_trends": bool(x_trends),
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
                source_health[response_key] = bool(
                    isinstance(source_status, dict) and source_status.get("available")
                )
            if not google_trends:
                errors.append("Google Trends 결과 없음")
            if not x_trends:
                errors.append("공개 X 트렌드 결과 없음")
            self._snapshot = {
                "available": bool(visible_items),
                "country": country,
                "items": visible_items,
                "total_candidates": len(candidates),
                "qualified_candidates": len(items),
                "breaking_news_count": len(breaking_items),
                "filtered_out_count": len(candidates) - len(items),
                "filter_summary": dict(filtered_reasons),
                "strict_materiality": True,
                "x_native_count": sum(1 for item in items if item.get("qualification_mode") == "x_native_history"),
                "expanded_news_count": expanded_news_count,
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
                "refreshed_at": now.isoformat(),
                "source_health": source_health,
                "errors": errors,
                "notice": "스포츠·정치·증시·기업 실적·부동산을 제외합니다. 뉴스 근거 없는 X 상위권 반복·상승 단어는 저신뢰도 X 네이티브 급등으로 분리하고, 연합뉴스·기상청 직접 발표는 점수 없는 별도 lane으로 병기합니다.",
            }
            return self.snapshot()
